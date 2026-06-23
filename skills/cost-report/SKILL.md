---
name: "cost-report"
description: "Aggregate per-session tool-timings into a project-wide spend report. Use when the operator asks for cost breakdown by project, by pipeline, or by agent role; when the model-efficiency report needs cost grounding; or as a periodic /loop check on harness spend. Advisory only — writes a markdown report, never modifies configs."
verdict: "COST_REPORT_READY"
phase: "utility"
dispatch: "skill-tool"
argument-hint: "Optional: --since YYYY-MM-DD or --out <path>"
---

# Cost Report

## When to Invoke

- **Operator request**: "show me what the harness cost this month", "which agents are burning the most tokens", "cost-per-PR by project".
- **Periodic check**: scheduled via `/loop` (e.g. weekly) so spend trends are visible without manual prompting.
- **Adjacent to `/harness:eval-model-effectiveness`**: that skill compares model success rates per role; this skill grounds those comparisons in dollars.
- **Do NOT use when**: a single pipeline's cost is the question — that lives on the per-pipeline observation record (`cost_estimate_usd`, written by `/harness:learn` per B12.2).

## Inputs

- **Pipeline state**: none (this is a utility skill, not gated by phase verdicts).
- **Filesystem**:
  - `~/.claude/metrics/*/tool-timings.jsonl` — per-session timing records.
    Each record has at least `model`, `input_tokens`, `output_tokens`,
    optionally `cache_creation_input_tokens`, `cache_read_input_tokens`,
    `agent_role`, `task_id`.
  - `~/.claude/metrics/costs.jsonl` — per-session `session_end` records
    written by `hooks/cost-tracker.sh`. Each `session_end` record carries
    a `preamble_tokens` field (estimated, bytes/3.5) and a `usage_by_model`
    field (real token counts per model, read from the transcript at session
    close). Used by Steps 2, 4, and 5-bis.
  - `hooks/_lib/cost_estimator.py` — `estimate_cost_usd` and
    `estimate_cost_usd_per_pipeline` (single source of truth for pricing).
- **External (optional)**: GitHub merged-PR list — used to attach a
  cost-per-PR figure to recent merges.

## Procedure

Numbered steps. Concrete commands. The skill is read by an agent (or invoked
as a one-shot script in a future iteration) — both paths follow this
procedure literally.

### Step 1: Discover per-session timing files

```bash
find "${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/metrics" -maxdepth 2 -name "tool-timings.jsonl" -type f
```

Filter by `--since YYYY-MM-DD` (file mtime) when the argument is given.

### Step 2: Compute per-pipeline cost from costs.jsonl

Read `~/.claude/metrics/costs.jsonl`, find all `session_end` records that
carry a `usage_by_model` field, and compute cost per `task_id`:

```python
import json, sys
sys.path.insert(0, f"{os.environ.get('CLAUDE_PLUGIN_ROOT') or os.path.join(os.path.expanduser('~'), '.claude')}/hooks/_lib")
from cost_estimator import estimate_cost_usd

def _usage_by_model_to_records(ubm):
    return [{"model": m, **counts} for m, counts in ubm.items()]

by_pipeline = {}
with open(costs_jsonl_path) as f:
    for line in f:
        rec = json.loads(line.strip())
        if rec.get("event") != "session_end":
            continue
        _tid = rec.get("task_id")
        task_id = _tid if (_tid and _tid != "none") else rec.get("session_id", "unattributed")
        ubm = rec.get("usage_by_model") or {}
        usd = estimate_cost_usd(_usage_by_model_to_records(ubm))
        by_pipeline[task_id] = by_pipeline.get(task_id, 0.0) + usd
# {task_id: usd, ...}
```

Note: `task_id` is populated by `hooks/cost-tracker.sh` from the active pipeline
at session close; records written when no pipeline was active carry `task_id: "none"`
and are treated as unattributed (fall back to `session_id`). Per-session and
per-pipeline totals are the reliable figures; per-subagent USD is not available.

### Step 3: Join with merged-PR data

Prefer the GitHub MCP tool when available:

```
mcp__github__list_pull_requests(state="merged", per_page=100)
```

Graceful fallback to shell when MCP is not connected (mirrors the
`gh-cache` MCP pattern documented in `protocols/agent-protocol.md`):

```bash
gh pr list --state merged --limit 100 --json number,title,mergedAt,headRefName
```

Match PR `headRefName` against pipeline `task_id` (the harness convention is
`{task-id}/{slice}` or `{task-id}` as the branch root) to attach a
cost-per-PR figure to recent merges. Unmatched pipelines remain in the
per-pipeline section without a PR linkage.

### Step 4: Per-agent-role attribution — not available from this source

Per-agent-role USD is **not derivable** from `costs.jsonl` `usage_by_model`
records. Each `session_end` record covers an entire Claude Code session; a
session may span multiple subagents whose turns interleave in the transcript.
The `cost-tracker.sh` Stop hook has no per-subagent breakout — it sums all
transcript turns into one `usage_by_model` dict with no `agent_role` field.

Omit the per-agent-role section from the report, or render the header with
a single honest line:

```markdown
## Top 3 Most Expensive Agents
Per-agent-role USD attribution is not available from session-level transcript
data (turns interleave across subagents). A future slice adding per-subagent
token capture would unlock this view.
```

### Step 5: Write the report

Path: `~/.claude/metrics/reports/{YYYY-MM-DD}-cost.md` (override with
`--out <path>`). Create parent directories if needed.

Sections (in order):

1. `## Total Spend (USD)` — single dollar figure with the date range covered.
2. `## Cost-per-PR by project` — table with columns `Project | PRs merged | Total cost USD | Avg cost per PR`. The "project" column derives from the GitHub remote of the matched PRs.
3. `## Top 3 Most Expensive Pipelines` — table `Rank | task_id | USD | PR (if matched)`.
4. `## Top 3 Most Expensive Agents` — honest note that per-agent-role USD is not available from session-level data (see Step 4).
5. `## Sandbox Verify Skip Rate` — operator-facing fleet-ops view of sandbox-verify health. Aggregates `metrics/*/sandbox-verify-skips.jsonl` via the shared helper:

   ```python
   import sys
   sys.path.insert(0, f"{os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')}/hooks/_lib")
   from sandbox_skip_rate import aggregate_skip_rate
   from pathlib import Path
   result = aggregate_skip_rate(Path(os.environ.get('CLAUDE_PLUGIN_DATA') or os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')) / "metrics")
   # {"reasons": {...}, "total_invocations": N, "skip_rate": float, "dropped_lines": N}
   ```

   Render as:

   ```markdown
   ## Sandbox Verify Skip Rate
   | Reason | Count |
   |---|---|
   | no-e2b-token | 12 |
   | env-hatch | 4 |
   | no-testable-changes | 2 |

   - Total invocations: 18
   - Skip rate: 100.0% (18 / 18)
   - Dropped lines (malformed JSONL): 0
   ```

   When `total_invocations == 0`, render the header with a single line `_No sandbox-verify invocations found in scanned metrics._` — the section is not omitted; an empty fleet is itself informative. When `dropped_lines > 0`, surface the dropped count so operators can investigate JSONL corruption.

6. `## Preamble Tokens (estimated, bytes/3.5)` — per-session preamble token
   counts read from `metrics/costs.jsonl` `session_end` records. Values are
   estimated (UTF-8 byte count ÷ 3.5) by `hooks/_lib/preamble-tokens-emit.py`
   at session close and written by `hooks/cost-tracker.sh`. Aggregated via the
   shared helper:

   ```python
   import sys
   sys.path.insert(0, f"{os.environ.get('CLAUDE_PLUGIN_ROOT') or os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')}/hooks/_lib")
   from preamble_tokens_aggregate import aggregate_preamble_tokens
   from pathlib import Path
   result = aggregate_preamble_tokens(Path(os.environ.get('CLAUDE_PLUGIN_DATA') or os.environ.get('CLAUDE_CONFIG_DIR') or os.path.join(os.path.expanduser('~'), '.claude')) / "metrics")
   # {"total_preamble_tokens": int, "session_count": int, "dropped_lines": int}
   ```

   Render as:

   ```markdown
   ## Preamble Tokens (estimated, bytes/3.5)
   - Total preamble tokens: 142,857
   - Sessions recorded: 23
   - Avg preamble tokens per session: 6,211
   - Dropped lines (malformed JSONL): 0
   ```

   `avg_per_session = total_preamble_tokens / session_count` (guard: when
   `session_count == 0` render `0`). When `session_count == 0`, render the
   header with a single line
   `_No session_end preamble records found in scanned metrics._` — the
   section is not omitted.

7. `## Notes` — any unknown-model warnings (collected from `cost_estimator` stderr) and dropped-record counts (malformed JSONL lines, records without `task_id`).

### Step 6: Emit verdict

```
Verdict: COST_REPORT_READY
Path: ~/.claude/metrics/reports/{YYYY-MM-DD}-cost.md
```

Always `COST_REPORT_READY` on success. Failures (no timing files found, all
records had unknown models, etc.) still write a report — the report itself
records the empty/degraded state. This skill never blocks downstream work.

## Output Format

Markdown report at the path above. Example skeleton:

```markdown
# Cost Report — 2026-05-04

Range: last 30 days. Files scanned: 47. Records processed: 12,394.

## Total Spend (USD)
**$184.32** across 23 pipelines.

## Cost-per-PR by project
| Project | PRs merged | Total USD | Avg/PR |
|---|---|---|---|
| ~/.claude | 12 | $98.40 | $8.20 |
| project-foo | 8 | $54.20 | $6.78 |

## Top 3 Most Expensive Pipelines
| Rank | task_id | USD | PR |
|---|---|---|---|
| 1 | wave5-hooks-bundle | $42.18 | #76 |
| 2 | cost-async-bundle | $19.04 | (open) |
| 3 | b12-batch | $14.22 | #74 |

## Top 3 Most Expensive Agents
Per-agent-role USD attribution is not available from session-level transcript
data (turns interleave across subagents). A future slice adding per-subagent
token capture would unlock this view.

## Preamble Tokens (estimated, bytes/3.5)
- Total preamble tokens: 142,857
- Sessions recorded: 23
- Avg preamble tokens per session: 6,211
- Dropped lines (malformed JSONL): 0

## Notes
- 2 records had unknown model `claude-experiment-x` (billed at $0.00).
- Records written before `task_id` injection (older sessions) bucket under their `session_id`.
```

## Safeguards

- **Advisory only.** Never modifies agent configs, never changes routing.
- **Pricing single-source.** `cost_estimator.PRICING_PER_MILLION` is the only
  pricing dict. Updates land there once; report consumers never embed prices.
- **Graceful on missing data.** Empty `metrics/` directories produce a report
  with `Total Spend: $0.00` and the empty-state notes — never an exception.

## Verdict

```
Verdict: COST_REPORT_READY
Next: human reviews; optional follow-up to /harness:eval-model-effectiveness for
      cost-grounded routing recommendations
Artifacts: ~/.claude/metrics/reports/{YYYY-MM-DD}-cost.md
```

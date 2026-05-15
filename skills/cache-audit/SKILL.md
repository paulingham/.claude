---
name: "cache-audit"
description: "Aggregate per-session cache.jsonl records into a project-wide prompt-cache read-ratio report. Use when the operator asks how effective prompt caching is, or as a periodic /loop check on harness cache discipline. Advisory only — writes a markdown report, never modifies configs."
verdict: "CACHE_AUDIT_READY"
phase: "utility"
dispatch: "skill-tool"
argument-hint: "Optional: --since YYYY-MM-DD or --out <path>"
---

# Cache Audit

## When to Invoke

- **Operator request**: "what's our prompt-cache hit rate", "which agents are missing the cache", "show me cache discipline trends".
- **Periodic check**: scheduled via `/loop` (e.g. weekly) so cache-stability regressions are visible without manual prompting.
- **Adjacent to `/cost-report`**: that skill grounds spend in dollars; this skill grounds cache health in `cache_read_input_tokens` ratios.
- **Do NOT use when**: a single pipeline's cache miss is the question — that lives in the per-spawn `metrics/{session}/cache.jsonl` records directly.

## Inputs

- **Pipeline state**: none (this is a utility skill, not gated by phase verdicts).
- **Filesystem**:
  - `~/.claude/metrics/*/cache.jsonl` — per-session prompt-cache token records emitted by `hooks/cost-feed.sh` (SubagentStop hook). Each record:
    `{ts, session_id, agent_role, input_tokens, cache_read_input_tokens, cache_creation_input_tokens, read_ratio}`.
  - `hooks/_lib/cost_estimator.py` — pricing single-source-of-truth used to attach dollar figures to cache_read vs. cache_create totals.
- **External (optional)**: none.

## Procedure

Numbered steps. Concrete commands.

### Step 1: Define the named target constant

The below-target threshold is a single named constant:

```
READ_RATIO_TARGET = 0.65
```

This value is the single source of truth — the report renders this exact value in the threshold sentence. To raise or lower the target, edit this constant and the test fixture in `tests/test_cache_audit_read_ratio_target_constant.py`.

### Step 2: Discover per-session cache files

```bash
find "$HOME/.claude/metrics" -maxdepth 2 -name "cache.jsonl" -type f
```

Filter by `--since YYYY-MM-DD` (file mtime) when the argument is given.

### Step 3: Aggregate per-session and per-agent

For each discovered file, parse each JSONL line. Compute:

- Per-session median `read_ratio` (one value per session).
- Per-agent median `read_ratio` (grouped by `agent_role`).
- Per-session token totals: `cache_read_input_tokens`, `cache_creation_input_tokens`, `input_tokens`.

### Step 4: Write the report

Path: `~/.claude/metrics/reports/{YYYY-MM-DD}-cache.md` (override with `--out <path>`). Create parent directories if needed.

Sections (in order):

1. `## Session Read Ratio Summary` — overall median and 90th-percentile read_ratio across all sessions; total token volume read vs. created.
2. `## Per-Agent Read Ratio` — table with columns `agent_role | sessions | median read_ratio | cache_read tokens | cache_create tokens`.
3. `## Below-Target Sessions` — sessions below `READ_RATIO_TARGET`. Render the threshold sentence verbatim with the literal target value: e.g. *"Sessions below 0.65 read_ratio target (the harness's `READ_RATIO_TARGET`):"*. The harness operates a staged-flip policy: `cache-flip-gate` skill evaluates 30-day P50 read_ratio; only when its verdict is `CACHE_FLIP_GATE_PASS` does the operator raise this constant further.
4. `## Notes` — disclosure of deferred anchors, harness shipping status, and known unmeasured surfaces (see § Disclosure below).

### Step 5: Emit verdict

```
Verdict: CACHE_AUDIT_READY
Path: ~/.claude/metrics/reports/{YYYY-MM-DD}-cache.md
```

Always `CACHE_AUDIT_READY` on success. Failures (no cache.jsonl files found, empty metrics dir) still write a report — the report itself records the empty/degraded state. The empty-metrics case still emits `CACHE_AUDIT_READY`. This skill never blocks downstream work.

## Disclosure

The `## Notes` section MUST disclose the prompt-caching breakpoint work's deferred surfaces. The hook `hooks/cache-breakpoint-injector.sh` is Path-B advisory at v2.1.140 — it computes resolved anchors but does not mutate `tool_input.prompt`. As of Slice C (2026-05-15), `persona-tail` is promoted to advisory; two anchors remain deferred.

Verbatim disclosure paragraph for the `## Notes` section (the aggregator MUST copy this paragraph into rendered reports):

> Prompt-caching breakpoint coverage is partial at v2.1.140. Two anchors are
> deferred by reason enum (matching `_lib/resolve-cache-breakpoints.py` payload):
> `protocol-splice-not-implemented` (protocol-tail anchor — no systematic
> protocol-body splice into spawn prompts), and
> `outside-hook-surface-v2.1.140` (tool-result-tail anchor — `messages[]` not
> exposed to hook envelope). The `persona-tail` anchor was promoted from
> deferred to advisory in Slice C (2026-05-15). Even after the
> `modified_tool_input` schema flip lands, `rules-core-tail` produces no cache
> reads until orchestrator-side splice of `rules/core.md` into
> `tool_input.prompt` lands (tracked as follow-up
> `prompt-caching-rules-core-splice`).

## Small-agent skip list

Three agents have preludes below the API minimum cacheable size (4096 tokens)
and are exempt from prompt-cache breakpoint enforcement. Verified empirically
2026-05-15: each agent's `agents/<name>.md` source is well under the 4096-token
floor.

- `planning-agent` (~1.4K tokens)
- `sandbox-verify-engineer` (~1.3K tokens)
- `vlm-critic` (~1.9K tokens)

The hook MAY skip cache-flag emission for these agents; the audit report MUST
exclude them from `## Below-Target Sessions` so their absent cache reads do
not depress the per-agent read_ratio.

## Output Format

Markdown report at the path above. Example skeleton:

```markdown
# Cache Audit — 2026-05-14

Range: last 30 days. Files scanned: 47. Records processed: 1,234.

## Session Read Ratio Summary
- Median session read_ratio: **0.72**
- 90th percentile: **0.91**
- Total cache_read tokens: 4,200,000
- Total cache_create tokens: 600,000
- Total input tokens: 1,400,000

## Per-Agent Read Ratio
| agent_role | sessions | median read_ratio | cache_read | cache_create |
|---|---|---|---|---|
| software-engineer | 23 | 0.78 | 1,800,000 | 240,000 |
| code-reviewer | 18 | 0.71 | 900,000 | 130,000 |
| architect | 12 | 0.62 | 400,000 | 100,000 |

## Below-Target Sessions
Sessions below 0.65 read_ratio target (the harness's `READ_RATIO_TARGET`):
| session_id | median read_ratio | spawns |
|---|---|---|
| abc12345 | 0.42 | 6 |

## Notes
- 4 records had unknown agent_role (bucketed as `unattributed`).
- Prompt-caching breakpoint coverage is partial at v2.1.140. Two anchors are deferred by reason enum (`protocol-splice-not-implemented` for protocol-tail; `outside-hook-surface-v2.1.140` for tool-result-tail). The `persona-tail` anchor was promoted from deferred to advisory in Slice C (2026-05-15). Even after the `modified_tool_input` schema flip lands, `rules-core-tail` produces no cache reads until orchestrator-side splice of `rules/core.md` into `tool_input.prompt` lands (tracked as follow-up `prompt-caching-rules-core-splice`).
```

## Safeguards

- **Advisory only.** Never modifies agent configs, never changes routing.
- **Threshold single-source.** `READ_RATIO_TARGET` is defined once in this skill at value 0.65 (see § Step 1). Updates land here, run tests, ship.
- **Graceful on missing data.** Empty `metrics/` directories produce a report with the empty-state notes — never an exception. The skill still emits `CACHE_AUDIT_READY` on the empty-metrics path.

## Verdict

```
Verdict: CACHE_AUDIT_READY
Next: human reviews; optional follow-up to /cost-report for dollar-grounded cache
      analysis
Artifacts: ~/.claude/metrics/reports/{YYYY-MM-DD}-cache.md
```

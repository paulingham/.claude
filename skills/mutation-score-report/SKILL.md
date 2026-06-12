---
name: "mutation-score-report"
description: "Aggregate per-session mutation-score signals into a convergence report showing soak progress toward the >=10 sessions / >=70% median promotion criterion. Use when the operator asks about mutation testing coverage, when evaluating whether the advisory mutation-score-gate.sh is ready to flip to enforcing, or as a periodic health check on the soak. Advisory only — writes a report, never modifies configs."
verdict: "MUTATION_SCORE_REPORT_READY"
phase: "utility"
dispatch: "skill-tool"
argument-hint: "Optional: --since YYYY-MM-DD or --out <path>"
---

# Mutation Score Report

## When to Invoke

- **Promotion check**: "Is the mutation-score-gate soak ready to flip to enforcing?" — the verdict
  section answers this directly.
- **Operator request**: "show me mutation test coverage across sessions", "what fraction of
  software-engineer runs had mutation tooling available?".
- **Periodic check**: scheduled via `/loop` (e.g. weekly) so convergence trends are visible.
- **Adjacent to `/harness:cost-report`**: that skill shows cost per role; this skill grounds
  mutation-testing quality for the same roles.
- **Do NOT use when**: a single pipeline's mutation report is needed — check the individual
  `mutation-score.jsonl` in that session's metrics directory directly.

## Inputs

- **Pipeline state**: none (utility skill, not gated by phase verdicts).
- **Filesystem**:
  - `$HARNESS_DATA/metrics/*/mutation-score.jsonl` — per-session mutation-score records written
    by `hooks/mutation-score-gate.sh`. Each record has at least:
    `timestamp`, `session_id`, `task_id`, `agent_role`, `changed_files_count`,
    `mutation_score` (null when tool not available), `tool_available` (bool), `note`.

## Procedure

### Step 1: Discover per-session mutation-score files

```bash
find "${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/metrics" \
  -maxdepth 2 -name "mutation-score.jsonl" -type f
```

Filter by `--since YYYY-MM-DD` (file mtime) when the argument is given.

### Step 2: Parse and aggregate records

For each discovered `mutation-score.jsonl`:

```python
import json, pathlib

records = []
for path in jsonl_paths:
    for line in pathlib.Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            dropped_count += 1

# Distinct session count (sessions that produced at least one record)
distinct_sessions = len({r["session_id"] for r in records})

# Scores where mutation_score is not null
real_scores = [r["mutation_score"] for r in records if r.get("mutation_score") is not None]

# Median score (guard: 0.0 when no real scores)
import statistics
median_score = statistics.median(real_scores) if real_scores else None

# Tool availability coverage %
tool_avail_count = sum(1 for r in records if r.get("tool_available") is True)
tool_avail_pct = (tool_avail_count / len(records) * 100) if records else 0.0
```

### Step 3: Evaluate promotion criterion

The promotion criterion (from `hooks/mutation-score-gate.sh` header):

> **>=10 distinct sessions with median changed-line mutation score >=70%
> AND zero false-blocks** before considering a flip to enforcing.

```python
sessions_met = distinct_sessions >= 10
score_met = median_score is not None and median_score >= 70.0
criterion_met = sessions_met and score_met
```

Verdict line:
- `CRITERION_MET` when both conditions are satisfied — the gate may be promoted to enforcing.
- `SOAK_IN_PROGRESS` otherwise — show what remains.

### Step 4: Write the report

Path: `$HARNESS_DATA/metrics/reports/{YYYY-MM-DD}-mutation-score.md`
(override with `--out <path>`). Create parent directories if needed.

Sections (in order):

1. `## Summary` — one-line soak status.
2. `## Distinct Sessions` — count of sessions that produced records.
3. `## Mutation Score Distribution` — median changed-line score (null when no real scores),
   list of per-session scores where available.
4. `## Tool Availability` — tool_availability coverage % across all records.
5. `## Promotion Criterion` — table with two rows (`sessions >=10` and `median score >=70%`),
   each showing current value + met/not-met status.
6. `## Verdict` — one of `CRITERION_MET` or `SOAK_IN_PROGRESS` with a short rationale.
7. `## Notes` — dropped-line counts, date range covered.

### Step 5: Emit verdict

```
Verdict: MUTATION_SCORE_REPORT_READY
Path: $HARNESS_DATA/metrics/reports/{YYYY-MM-DD}-mutation-score.md
```

Always `MUTATION_SCORE_REPORT_READY` on success. Failures (no
`mutation-score.jsonl` files found, all records malformed) still write a
report — the report itself records the empty/degraded state. This skill never
blocks downstream work.

## Output Format

Markdown report at the path above. Example skeleton:

```markdown
# Mutation Score Report — 2026-06-12

Range: all sessions. Files scanned: 23. Records processed: 41.

## Summary
Soak in progress: 7/10 sessions reached, median score unavailable (no tool).

## Distinct Sessions
**7** sessions produced mutation-score records.

## Mutation Score Distribution
- Median changed-line score: _unavailable_ (mutation tool not installed in any session)
- Per-session scores: (none recorded)

## Tool Availability
- Tool available: 0 / 41 records (0.0%)
- Tools detected: none

## Promotion Criterion
| Criterion | Required | Current | Met? |
|---|---|---|---|
| Distinct sessions | >=10 | 7 | NO |
| Median mutation score | >=70% | unavailable | NO |

## Verdict

**SOAK_IN_PROGRESS**

Remaining: need 3 more sessions; need mutation tool installed in at least one
session to compute a real score. Install `mutmut` (Python) or `stryker` (JS/TS)
in the project to start recording real scores.

## Notes
- Dropped lines (malformed JSONL): 0
- Date range: 2026-05-01 – 2026-06-12
```

## Safeguards

- **Advisory only.** Never modifies hook configs, never changes routing.
- **Graceful on missing data.** Empty `metrics/` directories produce a report
  with `distinct_sessions: 0` and the empty-state notes — never an exception.
- **Source of truth for JSONL path**: `hooks/mutation-score-gate.sh` writes to
  `mutation-score.jsonl`; this skill reads from `mutation-score.jsonl`. The
  filename is the contract between producer and consumer.

## Verdict

```
Verdict: MUTATION_SCORE_REPORT_READY
Next: human reviews; if CRITERION_MET, open a PR to flip mutation-score-gate.sh
      from advisory-log (exit 0) to enforcing (exit 2 on score <70%)
Artifacts: $HARNESS_DATA/metrics/reports/{YYYY-MM-DD}-mutation-score.md
```

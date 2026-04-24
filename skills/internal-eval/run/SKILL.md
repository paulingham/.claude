---
name: "internal-eval-run"
description: "Sub-skill of /internal-eval. Executes the inner pipeline per case under full isolation. Story 6 ships the single-case runner; Story 7 adds concurrency + orchestration."
context: fork
agent: software-engineer
---

# Internal Eval — Run

## Purpose

For each case in the suite, `run-case.sh` spawns an inner `/pipeline` that
implements the case's prompt, captures verdicts + cost + duration, and writes
`eval/runs/{run-id}/cases/{case-id}/result.json`. Isolation from the outer
pipeline is governed by the env-var contract in `ISOLATION.md` (Story 6a).

Story 7 builds concurrency + resumability + aggregation on top of this single
case-runner building block.

## Entry Point

```
skills/internal-eval/run/run-case.sh \
  --case-id <case-id> \
  --run-id <run-id> \
  [--harness-ref <sha>] \
  [--model opus|sonnet] \
  [--timeout <seconds>]  # default 1800 (30 min)
  [--dry-run]
```

Outputs a single `result.json` per case (schema below). Exits 0 on successful
write of result.json — the per-case *status* lives inside the JSON, not the
exit code. Callers (Story 7 orchestrator) aggregate statuses from JSON.

## Flags

| Flag | Default | Purpose |
|---|---|---|
| `--case-id` | required | Case directory name under `eval/cases/` |
| `--run-id`  | required | Run identifier; namespaces all output paths |
| `--harness-ref` | `live` | Pin inner pipeline to a specific `~/.claude` SHA via `git worktree add <path> <sha>`; `HOME` is re-rooted there so skill/hook/rule resolution reads from the pinned tree, not current `~/.claude`. Falsifiable: same case at two different SHAs where a skill differs produces different results. |
| `--model` | `opus` | Which model the inner agents default to |
| `--timeout` | `1800` | Per-case wall-clock timeout in seconds; on exceed → `failed_timeout` |
| `--dry-run` | off | Validate flags + isolation setup, skip inner-pipeline spawn. Emits `dry_run_ok`. Used by Story 7 orchestration smoke tests. |

## Isolation Contract

Every inner pipeline inherits the env-var contract in `ISOLATION.md`:

| Variable | Value |
|---|---|
| `CLAUDE_PIPELINE_TASK_ID` | `eval-${run-id}-${case-id}` |
| `CLAUDE_PIPELINE_BYPASS` | `1` |
| `CLAUDE_DISABLE_AUTO_LEARN` | `1` |
| `CLAUDE_PROJECT_HASH` | `eval-${run-id}-${case-id}` |
| `EVAL_RUN_ID` | `${run-id}` |
| `EVAL_CASE_ID` | `${case-id}` |
| `HOME` | `eval/runs/${run-id}/home/${case-id}` shadow root |

Inner `pipeline-state/` lives under `eval/runs/${run-id}/inner/${case-id}/` —
never shared `pipeline-state/`. Cost records filter via
`${HOME}/metrics/costs.jsonl` for matching `EVAL_RUN_ID` + `EVAL_CASE_ID`.

Kill-mid-run guarantee: outer `pipeline-state/` has zero `eval-${run-id}-*`
residue if the inner is killed. Enforced by construction — inner writes only
under its shadow HOME.

## Per-Case Status Enum (B4)

Exactly one is emitted per case:

| Status | Meaning | Counts as regression? |
|---|---|---|
| `passed` | Inner pipeline completed AND all gates green (review=APPROVE, verify=VERIFIED, qa=COVERED, accept=APPROVED) | N/A (baseline) |
| `failed_diff` | Ran to completion but one or more gates NOT green | Yes |
| `failed_build` | Inner pipeline errored mid-flight (build failure, worktree corruption) | Yes |
| `failed_timeout` | Wall-clock `--timeout` exceeded | No (neutral) |
| `failed_infra` | Harness-side failure (worktree creation, harness-ref checkout, HOME shadow setup). NEVER a regression. | No |
| `dry_run_ok` | `--dry-run` was set; inner pipeline skipped | No |

Only `passed` counts for the headline pass-rate. `failed_infra` and
`failed_timeout` are excluded from regression accounting (Story 8).

## result.json Schema

```json
{
  "case_id": "<case>",
  "run_id": "<run>",
  "status": "<enum above>",
  "duration_sec": 123.4,
  "cost_usd": 0.0,
  "review_rounds": 0,
  "rework": false,
  "harness_ref": "<sha>|live",
  "model": "opus",
  "flakiness_tier": "deterministic",
  "scoring_mode": "test-passing",
  "timestamp": "2026-04-24T00:00:00Z",
  "inner_pipeline_state": "<path>",
  "failure_reason": "<human-readable or empty>"
}
```

Strict scoring detail is deferred to Story 8; this sub-skill emits only the
STATUS ENUM + shape. Story 8 will extend `scoring.sh` with oracle-test
execution for `scoring_mode=test-passing`.

## Test Hooks

- `EVAL_RUNS_DIR=<path>` — override the default `eval/runs/` root (used by tests)
- `EVAL_INNER_STUB=<script>` — inject a fake inner pipeline for fast hermetic
  testing. The stub is called with `<run_dir> <inner_state_dir>` args and its
  exit code is mapped via `rc_to_status`. Story 7 replaces this with real
  `/pipeline` dispatch.
- `CLAUDE_HARNESS_REPO=<path>` — override the git repo that `resolve_harness_root`
  worktree-adds from (default `$HOME/.claude`). Used by the harness-ref pinned
  fixture test to prove different SHAs produce different trees.

## Lib Decomposition

| File | Responsibility |
|---|---|
| `lib/args.sh` | Flag parser (sets CASE_ID, RUN_ID, HARNESS_REF, MODEL, TIMEOUT_SEC, DRY_RUN) |
| `lib/isolation.sh` | Env-var composition + shadow HOME / inner state paths |
| `lib/harness-ref.sh` | SHA resolution + worktree-add for pinned harness |
| `lib/timeout.sh` | Portable `run_with_timeout` (GNU `timeout` with bash fallback) |
| `lib/scoring.sh` | Strict-binary gate→status mapping (Story 8 extends with oracles) |
| `lib/status.sh` | Status enum + `write_result_json` |
| `lib/result-emit.sh` | `rc_to_status`, `rc_reason`, `emit_status` (result.json writer wrapper) |
| `lib/runner.sh` | `main` + inner-pipeline dispatch |

## Verdict

`BUILD_COMPLETE` for Story 6 means: `run-case.sh` with the above flags, the
decomposed libs under `lib/`, the status enum, and `test_run_case.sh` covering
isolation env vars, shadow HOME location, inner-state path, harness-ref live +
pinned, timeout → failed_timeout, passed status, failed_infra fallback,
result.json schema, and dry-run short-circuit.

Suite-level verdict (EVAL_PASSED / EVAL_FAILED) is emitted by the parent
`/internal-eval` skill after Story 7 orchestrates many of these and Story 8
aggregates + diffs.

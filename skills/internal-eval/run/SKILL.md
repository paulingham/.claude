---
name: "internal-eval-run"
description: "Sub-skill of /harness:internal-eval. Executes the inner pipeline per case under full isolation. Story 6 ships the single-case runner; Story 7 adds concurrency + orchestration."
context: fork
agent: software-engineer
---

# Internal Eval — Run

## Purpose

For each case in the suite, `run-case.sh` spawns an inner `/harness:pipeline` that
implements the case's prompt, captures verdicts + cost + duration, and writes
`eval/runs/{run-id}/cases/{case-id}/result.json`. Isolation from the outer
pipeline is governed by the env-var contract in `ISOLATION.md` (Story 6a).

Story 7's `run-suite.sh` wraps `run-case.sh` with concurrency, resumability,
and aggregation — this is the entry point the `/harness:internal-eval` skill (Story
12) will ultimately invoke. See § Suite Orchestration below.

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
  testing. When set, the stub is called with `<run_dir> <inner_state_dir>` args
  and its exit code is mapped via `rc_to_status`. When unset, the runner
  invokes the real `claude` CLI against the case's `task.md`.
- `EVAL_CLAUDE_BIN=<path>` — override the `claude` binary resolved by the real
  dispatch path (default: `claude` on PATH). Missing binary → `failed_infra`.
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
`/harness:internal-eval` skill after Story 7 orchestrates many of these and Story 8
aggregates + diffs.

## Suite Orchestration (Story 7)

```
skills/internal-eval/run/run-suite.sh \
  --run-id <id> \
  [--suite default] \
  [--model opus|sonnet] \
  [--harness-ref <sha>] \
  [--concurrency N]   # default 4
  [--resume]
  [--preamble none|decision-ladder]
```

| Flag | Default | Purpose |
|---|---|---|
| `--run-id` | required | Namespaces all output paths under `eval/runs/<id>/` |
| `--suite` | `default` | `default` expands to `eval/cases/*` minus `_example/` and `.candidates/`; any other value is treated as a literal case-id (single-case mode) |
| `--model` | `opus` | Threaded to every `run-case.sh` invocation |
| `--harness-ref` | empty → live | SHA to pin; ONE shared worktree created at suite start and reused across every case (not per-case) |
| `--concurrency` | `4` | Max parallel `run-case.sh` workers (bash-3.2-compatible pool) |
| `--resume` | off | Skip any case whose `cases/<id>/result.json` already exists on disk |
| `--preamble` | `decision-ladder` | `none` strips the Decision Ladder block from the harness worktree's agent + SKILL files before dispatch (arm A); `decision-ladder` leaves them unchanged (arm B). `none` requires `--harness-ref` — refuses to mutate live `~/.claude`. |

### Outputs (per run)

```
eval/runs/<run-id>/
  suite.json           # run-level state (status: running|completed|interrupted)
  harness-wt/          # shared harness-ref worktree (only when --harness-ref given)
  cases/<case-id>/
    result.json        # written by run-case.sh
    inner/             # inner pipeline state (Story 6 isolation)
  home/<case-id>/      # shadow HOME per case (Story 6 isolation)
  aggregate.json       # written after all cases complete (also on interrupt)
  cases.json           # scorer-readable projection: [{case, pass, loc_added, loc_removed, input_tokens, output_tokens}, …]
```

#### cases.json — scorer input

Written by `lib/suite-cases-json.sh:write_cases_json` at the end of the run (and on signal interrupt). Consumed directly by `score/ab-compare.sh`. Schema per element:

| Key | Type | Source |
|---|---|---|
| `case` | string | case directory name |
| `pass` | bool | `status == "passed"` |
| `loc_added` | int | `inner/<case>/net-numstat` field 1 (optional; 0 when absent) |
| `loc_removed` | int | `inner/<case>/net-numstat` field 2 (optional; 0 when absent) |
| `input_tokens` | int | sum of `costs.jsonl` records with `eval_run_id` + `eval_case_id` matching |
| `output_tokens` | int | same records, `output_tokens` field |

**net-numstat optional-input contract.** The inner pipeline does NOT yet emit `net-numstat`. A future ship-step writes `${EVAL_RUNS_DIR}/${EVAL_RUN_ID}/inner/${EVAL_CASE_ID}/net-numstat` as `<added>\t<removed>` — all path components are derivable from already-exported env vars with no extra plumbing. Until then, `loc_added` and `loc_removed` are 0 for every case (documented gap; caveats block in the ab-report flags this).

**failed_infra cases ARE included.** They appear in cases.json with `pass:false` and affect the safety denominator — intentional (they represent completed-but-broken runs). This differs from `aggregate.json` pass_rate which excludes infra failures from the denominator.

### aggregate.json Schema

```json
{
  "run_id": "...", "suite": "...", "model": "opus", "harness_ref": "...",
  "total_cases": 10, "passed": 7,
  "failed_diff": 1, "failed_build": 1, "failed_timeout": 0, "failed_infra": 1,
  "pass_rate": 0.777,
  "total_duration_sec": 12.3, "total_cost_usd": 0.42,
  "completed_at": "2026-04-24T09:20:00Z",
  "case_results": [{"case_id": "c1", "status": "passed"}]
}
```

`pass_rate = passed / (total_cases - failed_infra)`. `failed_infra` is
excluded from the denominator (plan validation B4/B6): harness-side failures
never count as regressions. If `total_cases - failed_infra == 0`, `pass_rate`
is `0`.

### Signal Handling

`run-suite.sh` traps `INT` and `TERM`. On signal: a partial `aggregate.json`
is written (whatever cases completed so far), `suite.json.status` flips to
`interrupted`, and the process exits 130. Note: background bash scripts
ignore SIGINT by default (POSIX job-control); production CI and the test
suite both send SIGTERM for cancellation.

### Resumability

`--resume` skips any case whose `eval/runs/<run-id>/cases/<case-id>/result.json`
already exists on disk. First run executes all cases; `--resume` runs work
through the remainder. Aggregation reads every result.json on disk —
existing + newly-written — so prior results are preserved end-to-end.

### Concurrency

The job pool uses `jobs -r -p | wc -l` as the gate (bash-3.2 compatible; no
`wait -n`). At most `--concurrency` workers run at any time; cases beyond
that queue waiting for a slot. Each worker is an independent
`bash run-case.sh` invocation — results are written to disk by the worker,
not piped back.

### A/B Measurement — How to Run (post-merge, operator-explicit)

**BUILD does NOT authorize RUNning the 2-arm measurement.** The operator must explicitly invoke the run — each arm spawns full nested `claude -p /pipeline` calls for every case (~30 min timeout each); 2 arms × n cases ≈ 1-2 hr + large token spend.

Post-merge 2-command recipe (requires `--harness-ref <sha>` pointing to a SHA before the ladder was merged):

```bash
# Arm A — no decision ladder (control)
run-suite.sh --run-id ladder-a --suite default --harness-ref <pre-ladder-sha> \
  --preamble none

# Arm B — with decision ladder (treatment); use live (no --harness-ref needed)
run-suite.sh --run-id ladder-b --suite default \
  --preamble decision-ladder

# Compare
score/ab-compare.sh --arm-a ladder-a --arm-b ladder-b --preamble-b decision-ladder
```

### Interpreting Results

- **Directional only at n<10.** One case flip = 100/n% safety swing. Results are not distinguishable from single-run LLM variance without replication.
- **Test-pass-rate proxy.** Without mutation score, safety is binary pass/fail per case — a coarse signal.
- **LOC gap.** `loc_added`/`loc_removed` are 0 until the inner pipeline emits `net-numstat`. Verdict turns on USD-win or safety only.
- **Always replicate.** Run at least 3× per arm before acting on a verdict.
- **If verdict is always NEUTRAL or INSUFFICIENT**, inspect `cases.json` in both run dirs to confirm cases completed and `pass:true` entries exist in at least one arm.
- **Strip re-validation.** If `agents/software-engineer.md` or `agents/frontend-engineer.md` are restructured (headings added/removed before the `## Decision Ladder` section), re-validate the strip by running B1 and B2 tests manually.

### Lib Decomposition (Story 7 additions)

| File | Responsibility |
|---|---|
| `lib/suite-args.sh` | Flag parser for run-suite (separate from run-case `args.sh`); `--preamble` + B5 guard |
| `lib/suite-resume.sh` | `case_already_done`, `filter_pending_cases` |
| `lib/suite-aggregate.sh` | Reads per-case result.json, writes aggregate.json |
| `lib/suite-aggregate.jq` | jq program computing counts + pass_rate |
| `lib/suite-harness.sh` | One-time shared harness-ref worktree (wraps `resolve_harness_root`) |
| `lib/suite-pool.sh` | Bash-3.2 job pool (`run_pool <max> <launcher_fn> <case...>`) |
| `lib/suite-enumerate.sh` | `enumerate_cases` (default-suite glob) |
| `lib/suite-state.sh` | `write_suite_state` (suite.json writer) |
| `lib/suite-dispatch.sh` | `dispatch_case` — launcher the pool calls per case |
| `lib/suite-main.sh` | `suite_main` orchestrator composing the above |
| `lib/suite-cases-json.sh` | `write_cases_json` — projects result.json + costs.jsonl into cases.json |
| `lib/suite-preamble.sh` | `strip_ladder_from_harness` — strips Decision Ladder from wt copies when `--preamble none` |

### Test Hooks

- `EVAL_CASES_DIR=<path>` — override default `eval/cases/` root (used by tests)
- `EVAL_RUNS_DIR=<path>` — override default `eval/runs/` root (shared with run-case)
- `EVAL_INNER_STUB=<script>` — inherited by every case; stubs the inner pipeline
- `CLAUDE_HARNESS_REPO=<path>` — override the repo that `--harness-ref` worktree-adds from

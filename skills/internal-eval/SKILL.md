---
name: "internal-eval"
description: "Eval phase: suite execution, baseline capture, and regression diff across captured real-world harness cases. Runs the agent pipeline against a fixed case set, compares against a stored baseline, and emits a pass/fail verdict on regressions."
context: fork
agent: software-engineer
argument-hint: "run | capture backfill | capture promote <case-id> | inspect <case-id>"
---

# Internal Eval

## What This Skill Does

Runs the harness against a suite of captured real-world cases (stored under `eval/cases/`), scores each case against its oracle, and diffs the result set against a baseline. Produces a regression verdict that gates harness changes: the harness must not silently degrade on the cases we already know how to solve.

This skill is the orchestration shell. The heavy lifting lives in three sub-skills:
- `capture/` — turning real merged PRs into promoted cases
- `run/` — executing the inner pipeline per case under isolation
- `score/` — oracle scoring + baseline diff + report rendering

## Entry Commands

| Command | Purpose |
|---|---|
| `/internal-eval run [--suite default] [--model opus] [--harness-ref <sha>] [--baseline]` | Run the suite. `--baseline` stamps results as the new baseline instead of diffing against one. |
| `/internal-eval capture backfill --limit N` | Scan recent merged PRs for oracle-matching candidates, write to `eval/cases/.candidates/`. |
| `/internal-eval capture promote <case-id>` | Promote a candidate from `.candidates/` into `eval/cases/` (becomes part of the suite). |
| `/internal-eval inspect <case-id>` | Diagnostic: show per-case metadata, latest result, oracle diff. Populated by Story 8. |

## Process

### Step 1: Resolve inputs

1. Parse the subcommand and flags. `run` is the default if unspecified.
2. Resolve `--harness-ref` to a SHA via `git rev-parse`. If omitted, use `HEAD`.
3. Resolve `--suite` to a directory under `eval/suites/`; default `eval/suites/default.txt` is the list of promoted case IDs.

### Step 2: Gate on case availability

Count promoted cases under `eval/cases/` that match the suite filter:
- If zero → emit `INSUFFICIENT_CASES` and exit 0. This is NOT an error: it means the suite is empty and the harness is uncovered, which the operator must address by running `/internal-eval capture backfill` + `capture promote`.
- If ≥ 1 → continue to Step 3.

### Step 3: Dispatch the run

Delegate to `skills/internal-eval/run/SKILL.md`. The run sub-skill is responsible for isolation (see `run/ISOLATION.md` for env-var contract), per-case timeouts, cost ceilings, and writing per-case result JSON under `eval/runs/{run-id}/cases/{case-id}/result.json`.

### Step 4: Score and diff

Delegate to `skills/internal-eval/score/SKILL.md`. The score sub-skill computes per-case pass/fail against the oracle, then diffs the run against the baseline (4 quadrants: regressions, improvements, removed, added). Writes `eval/runs/{run-id}/report.md`.

### Step 5: Emit verdict

- `--baseline` flag set → write the run's results to `eval/baseline.json` with `harness_ref` SHA + timestamp stamp; emit `EVAL_BASELINE_CAPTURED`.
- Otherwise, if any deterministic case shows a regression (pass→fail in the diff) → emit `EVAL_FAILED` and surface the regressions in the report.
- Otherwise → emit `EVAL_PASSED`.

## Verdict

| Verdict | Meaning |
|---|---|
| `EVAL_PASSED` | Suite ran, no deterministic regressions vs baseline. |
| `EVAL_FAILED` | Suite ran, ≥ 1 deterministic case regressed (pass→fail) vs baseline. |
| `EVAL_BASELINE_CAPTURED` | `--baseline` mode: results stamped as the new baseline. No diff performed. |
| `INSUFFICIENT_CASES` | Zero promoted cases matched the suite. Exit 0. Operator must capture + promote cases. |

## Phase Output

```
Verdict: EVAL_PASSED | EVAL_FAILED | EVAL_BASELINE_CAPTURED | INSUFFICIENT_CASES
Run ID: {run-id}
Harness ref: {sha}
Cases executed: {N}
Report: eval/runs/{run-id}/report.md
```

## Prerequisite

- `eval/cases/` exists (scaffolded by Story 1).
- Baseline stamped at least once via `/internal-eval run --baseline` before `EVAL_FAILED` is meaningful. Without a baseline, runs emit `EVAL_PASSED` with a note that no baseline exists.

## Anti-Patterns

- Running the suite against uncommitted harness state — always pin to a SHA via `--harness-ref`.
- Promoting a candidate without reviewing its oracle — the suite is only as trustworthy as its cases.
- Treating `failed_infra` as a regression — infra failures NEVER count (see Story 8 status enum).

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

This skill is the orchestration shell. The heavy lifting lives in four sub-skills:
- `capture/` — turning real merged PRs into promoted cases
- `run/` — executing the inner pipeline per case under isolation
- `score/` — oracle scoring + baseline diff + report rendering
- `validate/` — **delivery validation**: proves the baseline → inject → diff → restore → confirm-clean flow end-to-end with a stubbed inner pipeline. See `validate/SKILL.md`. Run via `bash skills/internal-eval/validate/run-validation-sequence.sh`.

## Entry Commands

| Command | Purpose |
|---|---|
| `/internal-eval run [--suite default] [--model opus] [--harness-ref <sha>] [--baseline]` | Run the suite. `--baseline` stamps results as the new baseline instead of diffing against one. |
| `/internal-eval capture backfill [--limit N] [--since YYYY-MM-DD]` | Scan recent merged PRs via `gh pr list`, oracle-filter through `capture/oracle-paths.json`, write candidates to `eval/cases/.candidates/{case-id}/` (5 artifacts each) + exclusion report to `eval/.candidates/.exclusion-report-{ISO}.md`. Privacy-gated: requires `eval/.privacy-acked` marker. |
| `/internal-eval capture promote <case-id>` | Atomically move `eval/cases/.candidates/{case-id}/` → `eval/cases/{case-id}/`. Validates `metadata.json`; refuses if destination already exists. |
| `/internal-eval inspect <case-id>` | Diagnostic: show per-case metadata, latest result, oracle diff. Populated by Story 8. |

## Process

### Step 0: Grader Isolation

Before the agent runs, oracle/grader files MUST be moved out of the case directory so the
agent cannot read or import them. This closes the reward-hack class where the agent
inspects `grader.py` (or `grader.sh`) and tailors its diff to satisfy the oracle's literal
checks rather than solving the task.

For each `eval/cases/<case-id>/grader.{py,sh}` (and any `oracle.py` / `oracle.sh` sibling):

1. Compute a quarantine path under a tmp directory the agent's shadow `HOME` cannot reach:
   `mktemp -d -t graders.XXXXXX` (outside `eval/runs/<run-id>/home/<case-id>/`).
2. `mv` the grader file from the case directory to the quarantine path. Record the
   original path and quarantine path in a manifest (`eval/runs/<run-id>/cases/<case-id>/grader-manifest.json`).
3. Run the agent. Inner-pipeline isolation already restricts `HOME` (see
   `run/ISOLATION.md`), so the agent has no path to the quarantined files.
4. After the agent has produced its candidate diff and exited, restore each grader by
   `mv`-ing it back from the quarantine path to the case directory. Verify byte-equivalence
   against the manifest's recorded SHA256 — if a grader was modified, fail the case as
   `failed_infra` (the agent reached files it should not have).
5. Score the candidate diff against the now-restored grader.

The `eval-anti-hack-lint.sh` PostToolUse hook (see `hooks/eval-anti-hack-lint.sh`) provides
defense-in-depth: it greps the candidate's changed files for known
grader-introspection patterns (`sys._getframe`, `inspect.stack`,
`unittest.TestCase.run`, `pytest.hookimpl`, custom `__getattr__` on assert results)
and emits `eval-hack-suspects.jsonl` + exit 2 on match. A clean run produces no
suspects.

Failure modes:
- Grader file missing post-run → agent deleted it → `failed_infra`
- Grader file modified post-run → agent tampered with it → `failed_infra`
- Lint hook flagged hack pattern → `failed_diff` with `failure_reason: "anti-hack-lint"`

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

- `--baseline` flag set → delegate to `score/capture-baseline.sh --run-id {id}` which writes `eval/baselines/{YYYY-MM-DD}-{model}.md` (YAML frontmatter: harness_ref, timestamp, run_id, counts) and updates the `latest-{model}.md` symlink; emit `EVAL_BASELINE_CAPTURED`.
- Otherwise, delegate to `score/diff-vs-baseline.sh --run-id {id}` which writes `regression.json` + `regression.md`. If `regression_count > 0` → emit `EVAL_FAILED`. Otherwise → emit `EVAL_PASSED`.
- Regression math operates on the intersection of harness-ref-compatible, non-quarantined cases. `failed_infra` and `failed_timeout` are neutral and never count as regressions.

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
- Baseline stamped at least once via `/internal-eval run --baseline` (produces `eval/baselines/{YYYY-MM-DD}-{model}.md` + `latest-{model}.md` symlink) before `EVAL_FAILED` is meaningful. Without a baseline, runs emit `EVAL_PASSED` with a note that no baseline exists.

## Anti-Patterns

- Running the suite against uncommitted harness state — always pin to a SHA via `--harness-ref`.
- Promoting a candidate without reviewing its oracle — the suite is only as trustworthy as its cases.
- Treating `failed_infra` as a regression — infra failures NEVER count (see Story 8 status enum).

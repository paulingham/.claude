---
name: "internal-eval-score"
description: "Sub-skill of /internal-eval. Scores per-case results against oracles, captures baselines, and diffs the run against the baseline across 4 quadrants."
context: fork
agent: software-engineer
---

# Internal Eval — Score

## Entry Points

| Script | Purpose |
|---|---|
| `capture-baseline.sh --run-id <id>` | Snapshot `eval/runs/{id}/aggregate.json` into `eval/baselines/{YYYY-MM-DD}-{model}.md`; updates `latest-{model}.md` symlink |
| `diff-vs-baseline.sh --run-id <id> [--baseline path]` | Emit `regression.json` + `regression.md` under the run dir; verdict `EVAL_FAILED` if any regression |

Library modules in `score/lib/` (all ≤50 lines): `baseline-args`, `baseline-write`, `baseline-parse`, `regression-args`, `regression-compute`, `compat-window`, `compat-filter`, `quadrants.jq`, `regression-md`.

## Purpose

1. Score each case result against its oracle per the case's `scoring_mode`.
2. Capture a baseline snapshot from an aggregate run (`capture-baseline.sh`).
3. Diff the current run against that baseline across 4 quadrants (`diff-vs-baseline.sh`).
4. Produce `regression.json` + human-readable `regression.md`; emit `EVAL_PASSED` / `EVAL_FAILED`.

## Scoring Modes (per-case, Story 8 A10)

Declared in each case's `metadata.json`:
- `exact` — byte-equal diff compare
- `normalized` — whitespace/ordering-normalized compare
- `test-passing` (default) — run the case's oracle tests against the candidate diff

## Flakiness Tiers (Story 8 A7)

Per-case `flakiness_tier`:
- `deterministic` — strict regression rule applies
- `retriable-2x` — retried up to 2x; auto-promoted from deterministic after 2+ consecutive unchanged-harness regressions
- `quarantined` — excluded from headline score, listed in report

Only `deterministic` cases gate the suite verdict.

## Baseline Diff Quadrants (Story 8 B6)

Computed on the intersection of cases present in both runs (honoring `min_harness_ref` / `max_harness_ref` compatibility windows):

| Quadrant | Definition | Effect |
|---|---|---|
| `regressions` | pass→fail | Fail the suite (deterministic only) |
| `improvements` | fail→pass | Record in report |
| `removed` | in baseline only | Neutral |
| `added` | in current only | Neutral |

## Neutrality Rules

- `failed_infra` — harness infra failure, NEVER a regression (runner bug, not model bug)
- `failed_timeout` — wall-clock timeout, NEVER a regression (handle via timeout tuning)
- `quarantined` cases — excluded from both regression count AND intersection count

## Verdict

- `regression_count == 0` → `EVAL_PASSED`
- `regression_count > 0`  → `EVAL_FAILED`

This sub-skill's output is consumed by the parent `/internal-eval` verdict.

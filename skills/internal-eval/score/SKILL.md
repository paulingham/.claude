---
name: "internal-eval-score"
description: "Sub-skill of /internal-eval. Scores per-case results against oracles and diffs the run against the baseline. Populated by Story 8 (scoring modes, flakiness tiers, 4-quadrant diff, report)."
context: fork
agent: software-engineer
---

# Internal Eval — Score

## Status

Stub. Populated by Story 8 (scoring modes, flakiness tiers, 4-quadrant baseline diff, report renderer, and the `inspect` subcommand details).

## Purpose

1. Score each case result against its oracle per the case's `scoring_mode`.
2. Diff the current run against `eval/baseline.json` across 4 quadrants.
3. Render `eval/runs/{run-id}/report.md` and decide pass/fail.

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

## Verdict

Populated by Story 8. This sub-skill produces inputs to the parent `/internal-eval` verdict (`EVAL_PASSED` vs `EVAL_FAILED`).

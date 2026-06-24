---
name: "internal-eval-score"
description: "Sub-skill of /harness:internal-eval. Scores per-case results against oracles, captures baselines, and diffs the run against the baseline across 4 quadrants."
context: fork
agent: software-engineer
---

# Internal Eval — Score

## Entry Points

| Script | Purpose |
|---|---|
| `capture-baseline.sh --run-id <id>` | Snapshot `eval/runs/{id}/aggregate.json` into `eval/baselines/{YYYY-MM-DD}-{model}.md`; updates `latest-{model}.md` symlink |
| `diff-vs-baseline.sh --run-id <id> [--baseline path]` | Emit `regression.json` + `regression.md` under the run dir; verdict `EVAL_FAILED` if any regression |
| `ab-compare.sh --arm-a <run-id> --arm-b <run-id> [--preamble-b <name>] [--suite default]` | A/B diff-economy comparison: reads per-case scored results for both arms, calls `lib/ab_compare.py`, renders `ab-report.md`. Advisory only — never gates. |

## A/B Safety-First Ladder (ab-compare.sh + lib/ab_compare.py)

Guard-return ladder (Iron Law 1 — a safety drop makes the improvement branch structurally unreachable):

1. `scored_A == 0 OR scored_B == 0` → `INSUFFICIENT` (IL8 fail-closed)
2. `safety_floor_held = (safety_B >= safety_A − EPSILON_SAFETY)`
3. `NOT floor_held` → `EVAL_REGRESSION_DETECTED` (improvement branch unreachable below)
4. Floor held: `EVAL_IMPROVEMENT_CONFIRMED` if `(loc_B < loc_A − EPS_LOC) OR (usd_B < usd_A − EPS_USD)`, else `EVAL_NEUTRAL`

### Epsilon defaults

| Constant | Default | Intent |
|---|---|---|
| `EPSILON_SAFETY_DEFAULT` | `0.0` | Exact floor — any real safety drop triggers regression |
| `EPS_LOC_DEFAULT` | `1` | LOC improvement needs strict win beyond 1-line noise |
| `EPS_USD_DEFAULT` | `0.01` | USD improvement needs >$0.01 win |

Config surface: `[ab]` block in `eval/config.yaml` (`epsilon_safety`, `eps_loc`, `eps_usd`); absent → module constants.

## Safety Proxy Disclosure

`safety_pct` = `pass_count / total_scored` (finite float, never None/crash). Mutation score surfaced additionally when a mutation artifact is present; otherwise falls back to test-pass-rate. The `ab-report.md` MUST include a `Safety proxy:` line per arm disclosing which metric was used.

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

This sub-skill's output is consumed by the parent `/harness:internal-eval` verdict.

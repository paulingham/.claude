# Case `metadata.json` Schema

Per-field semantics for every case's `metadata.json`. All 10 keys are **required**
(validated by `skills/internal-eval/tests/test_case_schema.sh`). Use `null` for
optional keys you want to leave unset (e.g. `max_harness_ref`).

## Fields

### `case_id` — string, required

Stable kebab-case identifier, matches the parent directory name. Example:
`"pr21-disable-reduce-perms"`. Used for:
- Per-case artifact paths under `eval/runs/{run-id}/{case-id}/`
- Cost attribution (`EVAL_CASE_ID` env var exported by the runner)
- Regression diff joins across runs (see Story 8)

### `classification` — string, required

One of: `"feature" | "refactor" | "bug-fix" | "tech-spike"`. Matches `/intake`'s
classification taxonomy so per-classification quality metrics line up with
observation records in `learning/{project-hash}/observations.jsonl`.

### `source_pr` — string, required

Canonical GitHub PR URL (or internal equivalent) the case was captured from. Used for
audit trail + enables re-capture if the case needs to be refreshed at a different
harness SHA. Use `""` for synthetic cases (`synthetic: true`).

### `min_harness_ref` — string, required

The earliest harness SHA the case is valid against. Captured at authoring time from
`git rev-parse HEAD` in `~/.claude/`. The runner SKIPS the case (does NOT fail it) if
run against a harness older than this SHA — see Story 7/8 compatibility windows.

### `max_harness_ref` — string | null, required

The latest harness SHA the case is valid against. `null` = no upper bound (case still
applies). Set to a SHA when a harness change intentionally invalidates the case (e.g.
a renamed skill removes the behavior the case exercises).

### `flakiness_tier` — string, required

One of: `"deterministic" | "retriable-2x" | "quarantined"`.
- `deterministic` (default) — strict regression rule applies (pass→fail ⇒ EVAL_FAILED)
- `retriable-2x` — runner retries up to 2x; strict rule applies after retry budget
- `quarantined` — excluded from headline score; listed in report for triage

Auto-promotion: 2+ consecutive unchanged-harness regressions → `retriable-2x`
(Story 8 enforces this).

### `scoring_mode` — string, required

One of: `"exact" | "normalized" | "test-passing"`.
- `exact` — candidate diff must be byte-identical to `golden-diff/` (rare; only for
  truly deterministic cases)
- `normalized` — whitespace/ordering-insensitive diff compare
- `test-passing` (default) — run oracle tests in `expected.md` against candidate diff
  applied to `context/`; pass iff all oracle tests green. Recommended default — robust
  to valid refactors.

### `timeout_minutes` — integer, required

Per-case wall-clock timeout. Default 30. On timeout → `failed_timeout` status (neutral
for regression gate per Story 8 B4/B6 amendments). Runner kills the inner pipeline
and records duration.

### `cost_ceiling_usd` — number, required

Per-case cost ceiling. Runner aborts the inner pipeline if cumulative agent cost
exceeds this (checked via `cost-tracker.sh` tagged with `EVAL_CASE_ID`). Abort →
`failed_infra` status (NEVER counts as regression — see Story 8 B6).

### `synthetic` — boolean, required

`true` if the case was hand-crafted rather than captured from a real merged PR.
Synthetic cases are de-prioritised by Story 3 (real PRs preferred, per Advisory A2)
and flagged in the report so reviewers know the provenance.

## Worked Example

See `metadata.json` in this directory for a filled-in example demonstrating all 10
required fields with representative values.

---
task_id: harness-opus-4-5-migration
slice_id: slice-a-model-binding-migration
branch: feat/harness-opus-4-5-migration/slice-a
phase: build
verdict: BUILD_FAILED
reason: iteration_cap_exhausted
head_sha: see-git-log
parent_sha: 1d557dd
tests_authored: 8
tests_green: 7
tests_red: 1
mutation_score_pct: not-measured
deviations:
  - id: scope-reduction-critical-path-only
    rationale: "Single-spawn 90-min time-box exceeded by Slice A's 44-file × 142-occurrence mechanical sweep + 12-test-stub batched-RED + new module + harness-audit wire-in + e2e + dual-accept aggregator + mutation testing + code-review dispatch. Reduced scope to highest-risk artefacts per pre-mortem; remaining sweep handed off via this build-state file."
    surface: "tests/test_no_residual_opus_4_7.py::test_zero_active_config_occurrences asserts the sweep is complete; currently RED listing remaining files"
  - id: bash-write-guard-blocks-batch-sed
    rationale: "Attempted batch sed across 22 remaining files blocked by hooks/bash-write-guard.sh; per-file Read+Edit cycle infeasible in remaining turn budget"
---

# Build State: Slice A (WIP)

## Status

**BUILD_FAILED — iteration_cap_exhausted (turn-budget).** Critical-path artefacts committed; mechanical sweep across ~22 remaining files incomplete. Single-spawn build cannot deliver Slice A as scoped in `plan.md` within the 90-min time-box.

## What landed (commits on `feat/harness-opus-4-5-migration/slice-a`)

1. `WIP feat(slice-a): migrate opus-4-7 → opus-4-5-20251101 (critical path)` — 20 files, 354+/18- LOC.
2. `WIP feat(slice-a): extend postmortem allowlist for test-infra + CLAUDE.md headers` — 2 files.

### Files migrated

- `agents/*.md` (all 25 frontmatter `model:`/`executor:`/`advisor:` fields → `claude-opus-4-5-20251101` or unchanged aliases).
- `hooks/_lib/cost_estimator.py` (added `claude-opus-4-5-20251101` pricing key; retained `claude-opus-4-7` key behind `DEPRECATED-REMOVE-AFTER-2026-05-22` comment for 7-day dual-accept rollback per MED-rate_version-rollback).
- `hooks/_lib/executor_resolver.py` (`CLAUDE_FORCE_OPUS` fallback → `claude-opus-4-5-20251101`).
- `hooks/cost-feed.sh` (`rate_version` token → `opus-4-5-2026-05`).

### New artefacts

- `hooks/_lib/model_allowlist.py` — public `check(repo_root) -> list[str]`, hard-coded `_ALLOWED` frozenset. Pure stdlib. ~70 LOC, cohesion-compliant (every function ≤30 LOC, CC ≤5, nesting ≤2).
- `skills/harness-audit/SKILL.md` — new step 3c invokes `model_allowlist.check()`.
- `tests/_fixtures/postmortem_allowlist.yaml` — schema documented inline.
- `tests/test_model_allowlist.py` — 2 tests, GREEN.
- `tests/test_cost_estimator_opus_4_5.py` — 3 tests, GREEN.
- `tests/test_no_residual_opus_4_7.py` — 3 tests; 2 GREEN (`test_postmortem_preserved`, `test_allowlist_fixture_well_formed`), 1 RED (`test_zero_active_config_occurrences` — the sweep gate, intentionally RED until residual files migrate).

### Test results (fresh, run at HEAD)

```
8 tests collected
7 passed
1 failed: tests/test_no_residual_opus_4_7.py::ZeroActiveConfigOccurrences::test_zero_active_config_occurrences
```

The single RED enumerates every residual file the continuation agent must migrate; the test IS the handoff checklist.

## What remains (continuation agent — DO IN ORDER)

### Step 1 — Complete the mechanical sweep

Run `tests/test_no_residual_opus_4_7.py::ZeroActiveConfigOccurrences::test_zero_active_config_occurrences`; the failure message enumerates each remaining `<file>:<lineno>: <preview>`. For each, decide:

- **Migrate the line** (`Read` then `Edit` — `bash-write-guard` blocks sed batches): replace `claude-opus-4-7` → `claude-opus-4-5-20251101`, `opus-4-7-2026-04` → `opus-4-5-2026-05`, bare `opus-4-7` → `opus-4-5`, and `Opus 4.7` → `Opus 4.5` where the surrounding prose is forward-looking config (not historical record).
- **Add to allowlist** when the reference is historical record OR test infrastructure that must keep referring to the legacy token (e.g. dual-accept regression tests).

Confirmed-residual files (from current RED output):

- `orchestrator/agent-orchestration.md`
- `README.md`
- `protocols/advisor-mode.md`
- `protocols/autonomous-intelligence.md`
- `scripts/probe-schema-flips.sh`
- `skills/security-review/SKILL.md`
- `skills/code-review/SKILL.md`
- `skills/patch-critique/SKILL.md`
- `skills/best-of-n/config.json`
- `skills/internal-eval/score/lib/regression-args.sh`
- `skills/internal-eval/score/stamp-pr-body.sh`
- `skills/internal-eval/tests/_lib/baseline_checks.sh`
- `skills/internal-eval/tests/_lib/stamp_checks.sh`
- `hooks/tests/test-eval-model-effectiveness.sh`
- `tests/test_pbt_engineer_frontmatter.py`
- `tests/test_executor_resolution.py`
- `tests/test_patch_critic.py`
- `tests/test_fix_engineer_routing.py`
- `tests/test_agent_executor_frontmatter.py`
- `tests/test_spec_blind_validator.py`
- `tests/shell/test_cost_feed.bats`
- `tests/shell/test_cost_feed_cache_emit.bats`

`internal-eval` baseline-fixture files (`*opus-4-7.md`, `latest-opus-4-7.md` symlinks) must also be **renamed** (not just sed'd) per the plan's `eval/baselines/` rename — these are filesystem artefacts.

### Step 2 — Author the still-missing test stubs (5 of 12 from plan table)

- `tests/test_executor_resolution.py` — add `test_fallback_returns_opus_4_5` (single-line extension; module already exists).
- `tests/test_advisor_resolver.py` — add `test_model_conditional_arms_use_4_5`. Caution: this file is allowlisted (it references the legacy token in regression assertions).
- `tests/shell/test_cost_feed.bats` — add `rate_version_bumped_to_opus_4_5`.
- `tests/test_cost_estimator_e2e.py` (new) — `test_cost_estimator_e2e_via_cache_jsonl_emit` (HIGH-E1 end-to-end through `cache-jsonl-emit.py`; proves A→B→C dependency).
- `tests/test_cost_report_dual_rate_version.py` (new) — `test_aggregator_accepts_both_tokens_during_window` (MED-rate_version-rollback).

### Step 3 — Wire the 7-day dual-accept window into `/cost-report`

Plan calls for `skills/cost-report/SKILL.md` to accept both `opus-4-7-2026-04` and `opus-4-5-2026-05` rate_version tokens for 7 days post-merge. The pricing-table dual-accept (already shipped) is necessary but not sufficient — the aggregator's `rate_version` filter is the other half.

### Step 4 — Mutation testing

Run `mutmut`/`cosmic-ray` against `hooks/_lib/model_allowlist.py` and the changed lines in `hooks/_lib/cost_estimator.py`. Iron Law 1 requires ≥70% mutation score on changed lines. If tooling unavailable, document the gap and proceed (Iron Law 1 is a build gate the orchestrator can choose to enforce or soak-warn).

### Step 5 — Cohesion & final commit

Re-run `tests/test_no_residual_opus_4_7.py` — must be GREEN before commit. Squash WIP commits if desired (current branch has 2 WIPs + 1 plan-state commit). Final commit message: `feat(slice-a): migrate opus-4-7 → opus-4-5-20251101 + model_allowlist audit`.

### Step 6 — Invoke `/code-review` as final Build step

Per pipeline protocol (Build phase final gate). Code-review reviews the full diff; orchestrator advances to Security Review on APPROVE.

## Critical risks honoured

- `CLAUDE.md:47` retains literal `Opus 4.7` (postmortem preserved — verified by `test_postmortem_preserved`, GREEN).
- `CLAUDE.md` L43-49 inline-paragraph range allowlisted (verified by `test_allowlist_fixture_well_formed`, GREEN).
- `protocols/_proposals/2026-05-14-narrow-xhigh-promotion.md` and `session-memory/` paths NOT touched (allowlist prefix match).
- Dual-accept window for `cost-report` aggregator: pricing dict half shipped. Aggregator filter half PENDING (continuation Step 3).

## Iron Law accounting

- IL1 (RED-first): RED test stubs authored BEFORE module changes for the new artefacts (`model_allowlist` + cost-table opus-4-5 key). RED test for the residual-sweep is authored and currently RED — sweep is the production "test passing" that proves migration completion.
- IL3 (no orchestrator code): all edits authored by this subagent.
- IL4 (HEAD on main): main repo HEAD unchanged; all writes via worktree `agent-229c827a` on branch `feat/harness-opus-4-5-migration/slice-a`.
- IL6 (in-cycle fixes, no follow-ups): the **scope reduction is a single-spawn-capacity issue, not a follow-up filing**. The plan as written cannot be delivered by one subagent in 90 minutes. This handoff requests a continuation spawn, NOT a future-pipeline follow-up. The orchestrator MUST dispatch the continuation to complete Slice A before advancing to Slice B/C.

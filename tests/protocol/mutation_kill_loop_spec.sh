#!/usr/bin/env bash
# Structural validator for the active, time-boxed Mutation Kill Loop protocol.
# All assertions are grep-based over the prose text of 6 harness markdown files.
# This IS the test — true automated unit tests are not meaningful for prose changes.
#
# Exit codes:
#   0 — all assertions passed
#   1 — one or more assertions failed (details printed to stdout)
#
# Usage:
#   bash tests/protocol/mutation_kill_loop_spec.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

ATDD="$REPO_ROOT/protocols/atdd-procedure.md"
INVARIANTS="$REPO_ROOT/protocols/engineering-invariants.md"
BUILD_IMPL="$REPO_ROOT/skills/build-implementation/SKILL.md"
SE_AGENT="$REPO_ROOT/agents/software-engineer.md"
QA_AGENT="$REPO_ROOT/agents/qa-engineer.md"
VERIFY_SKILL="$REPO_ROOT/skills/verify/SKILL.md"

FAILURES=0
PASSED=0

# ── helpers ──────────────────────────────────────────────────────────────────

pass() { echo "  PASS: $1"; PASSED=$(( PASSED + 1 )); }
fail() { echo "  FAIL: $1"; FAILURES=$(( FAILURES + 1 )); }

assert_contains() {
  local desc="$1"
  local file="$2"
  local pat="$3"
  if grep -qF -- "$pat" "$file"; then
    pass "$desc"
  else
    fail "$desc -- pattern not found: [$pat] in $file"
  fi
}

assert_contains_re() {
  local desc="$1"
  local file="$2"
  local pat="$3"
  if grep -qE -- "$pat" "$file"; then
    pass "$desc"
  else
    fail "$desc -- regex not found: [$pat] in $file"
  fi
}

# ── Slice A: AC1 — atdd step 4 active, time-boxed loop ───────────────────────

echo ""
echo "=== atdd_step4_defines_active_timeboxed_loop (AC1) ==="

assert_contains "AC1: atdd step 4 mentions Mutation Kill Loop" \
  "$ATDD" "Mutation Kill Loop"

assert_contains "AC1: atdd step 4 names env knob CLAUDE_MUTATION_KILL_BUDGET_SECONDS" \
  "$ATDD" "CLAUDE_MUTATION_KILL_BUDGET_SECONDS"

assert_contains "AC1: atdd step 4 names default 300" \
  "$ATDD" "default 300"

assert_contains "AC1: atdd step 4 names budget check at top of every round" \
  "$ATDD" "top of every round"

assert_contains "AC1: atdd step 4 stamps KILL_LOOP_START before first mutation run" \
  "$ATDD" "KILL_LOOP_START"

assert_contains "AC1: atdd step 4 stamps before first mutation run" \
  "$ATDD" "before the first mutation run"

# ── Slice A: AC3 — three outcomes and NO_PROGRESS before author ───────────────

echo ""
echo "=== atdd_step4_names_three_outcomes_and_orders_noprogress_before_author (AC3) ==="

assert_contains "AC3: REACHED outcome present" "$ATDD" "REACHED"
assert_contains "AC3: EXHAUSTED outcome present" "$ATDD" "EXHAUSTED"
assert_contains "AC3: NO_PROGRESS outcome present" "$ATDD" "NO_PROGRESS"

assert_contains "AC3: two-consecutive-zero-kill rule present" \
  "$ATDD" "two consecutive"

assert_contains "AC3: canonical order line places NO_PROGRESS check before authoring" \
  "$ATDD" "NO_PROGRESS check → author"

# ── Slice A: AC6 — append-not-clobber structure ──────────────────────────────

echo ""
echo "=== atdd_step4_specifies_append_not_clobber (AC6) ==="

assert_contains "AC6: atdd step 4 contains append" "$ATDD" "append"

assert_contains "AC6: atdd step 4 contains Kill-Loop Round heading" \
  "$ATDD" "### Kill-Loop Round"

assert_contains "AC6: atdd step 4 references single mutation-report artifact" \
  "$ATDD" "single mutation-report"

assert_contains "AC6: Tier-3.5-appends-below-Kill-Loop ordering documented" \
  "$ATDD" "appended BELOW"

# ── Slice A: AC7 — engineering-invariants Tier 3 threshold + cross-ref ────────

echo ""
echo "=== tier3_line_keeps_threshold_and_crossrefs_canonical_loop (AC7) ==="

assert_contains "AC7: engineering-invariants Tier 3 line still contains ≥70%" \
  "$INVARIANTS" "≥70%"

assert_contains "AC7: engineering-invariants Tier 3 line cross-refs atdd-procedure.md step 4 Mutation Kill Loop" \
  "$INVARIANTS" "atdd-procedure.md step 4 Mutation Kill Loop"

# ── Slice B: AC2 — build-implementation invokes loop by pointer + checklist ───

echo ""
echo "=== build_impl_invokes_loop_by_pointer_and_checklist (AC2) ==="

assert_contains "AC2: build-implementation Step 2 (3) points to atdd-procedure.md step 4" \
  "$BUILD_IMPL" "atdd-procedure.md step 4"

assert_contains "AC2: build-implementation Step 4 checklist has Mutation Kill Loop OUTCOME row" \
  "$BUILD_IMPL" "Mutation Kill Loop"

assert_contains "AC2: checklist row includes REACHED/EXHAUSTED/NO_PROGRESS" \
  "$BUILD_IMPL" "REACHED"

# ── Slice B: AC4 — software-engineer.md TDD Protocol points to loop ───────────

echo ""
echo "=== software_engineer_tdd_points_to_loop (AC4) ==="

assert_contains "AC4: software-engineer.md mentions active Mutation Kill Loop" \
  "$SE_AGENT" "Mutation Kill Loop"

assert_contains "AC4: software-engineer.md TDD Protocol references atdd-procedure.md step 4" \
  "$SE_AGENT" "atdd-procedure.md step 4"

# ── Slice B: AC5 — verify Tier 3 read-only note + qa-engineer aligned ─────────

echo ""
echo "=== verify_tier3_note_is_readonly_and_qa_aligned (AC5) ==="

assert_contains "AC5: verify/SKILL.md § 4 contains read-only-measuring note" \
  "$VERIFY_SKILL" "read-only"

assert_contains "AC5: verify/SKILL.md § 4 states active loop ran at Build" \
  "$VERIFY_SKILL" "Loop ran at Build"

assert_contains "AC5: verify/SKILL.md § 4 states MUST NOT write tests or commit" \
  "$VERIFY_SKILL" "MUST NOT write tests or commit"

assert_contains "AC5: qa-engineer.md Verify item states Tier 3 is read-only" \
  "$QA_AGENT" "read-only"

# ── Slice B: AC8 — freshness contract intact statement ───────────────────────

echo ""
echo "=== verify_note_states_freshness_intact (AC8) ==="

assert_contains "AC8: verify/SKILL.md § 4 states loop runs at Build before Final Gate" \
  "$VERIFY_SKILL" "before the Final Gate"

assert_contains "AC8: verify/SKILL.md § 4 states no mid-gate commits occur" \
  "$VERIFY_SKILL" "no mid-gate commits"

assert_contains "AC8: verify/SKILL.md § 4 states verification-evidence.json git_head freshness contract intact" \
  "$VERIFY_SKILL" "freshness contract is intact"

# ── Slice B: AC9 — Tier 3.5 Kill-Loop-aware dedup + append ───────────────────

echo ""
echo "=== tier35_dedups_latest_killloop_round_and_appends_below (AC9) ==="

assert_contains "AC9: verify/SKILL.md § 4.25 dedup references latest Kill-Loop round" \
  "$VERIFY_SKILL" "latest Kill-Loop round"

assert_contains "AC9: verify/SKILL.md § 4.25 append places Tier 3.5 below Kill-Loop rounds" \
  "$VERIFY_SKILL" "below any Kill-Loop rounds"

# ── Cross-slice consistency check ─────────────────────────────────────────────

echo ""
echo "=== crossrefs_enum_knob_and_no_disable_consistent (consistency) ==="

assert_contains "consistency: CLAUDE_MUTATION_KILL_BUDGET_SECONDS appears in atdd" \
  "$ATDD" "CLAUDE_MUTATION_KILL_BUDGET_SECONDS"

assert_contains "consistency: default 300 appears in atdd" \
  "$ATDD" "default 300"

assert_contains "consistency: REACHED appears in atdd" "$ATDD" "REACHED"
assert_contains "consistency: EXHAUSTED appears in atdd" "$ATDD" "EXHAUSTED"
assert_contains "consistency: NO_PROGRESS appears in atdd" "$ATDD" "NO_PROGRESS"

assert_contains "consistency: REACHED appears in build-implementation checklist" \
  "$BUILD_IMPL" "REACHED"

assert_contains "consistency: EXHAUSTED appears in build-implementation checklist" \
  "$BUILD_IMPL" "EXHAUSTED"

assert_contains "consistency: NO_PROGRESS appears in build-implementation checklist" \
  "$BUILD_IMPL" "NO_PROGRESS"

assert_contains "consistency: =0 is NOT a disable hatch stated in atdd" \
  "$ATDD" "=0"

assert_contains_re "consistency: atdd contains no-disable / Iron Law assertion" \
  "$ATDD" "(cannot be disabled|NOT.*disable|=0.*is NOT|Iron Law.*cannot)"

assert_contains "consistency: atdd pins =0 deterministically to 120 (floor rule, not 300)" \
  "$ATDD" "0 → 120"

# Verify cross-refs resolve: engineering-invariants → atdd step 4 loop
assert_contains "consistency: engineering-invariants cross-ref to atdd step 4 Mutation Kill Loop" \
  "$INVARIANTS" "atdd-procedure.md step 4 Mutation Kill Loop"

# Verify cross-refs resolve: build-implementation → atdd-procedure.md
assert_contains "consistency: build-implementation cross-ref to atdd-procedure.md" \
  "$BUILD_IMPL" "atdd-procedure.md"

# Verify cross-refs resolve: verify/SKILL.md → atdd-procedure.md step 4
assert_contains "consistency: verify/SKILL.md cross-ref to atdd-procedure.md step 4" \
  "$VERIFY_SKILL" "atdd-procedure.md step 4"

# Verify min-120 floor stated
assert_contains "consistency: minimum floor 120 stated in atdd" \
  "$ATDD" "120"

# ── Summary ───────────────────────────────────────────────────────────────────

echo ""
echo "=============================="
echo "Results: $PASSED passed, $FAILURES failed"
echo "=============================="

if [ "$FAILURES" -gt 0 ]; then
  exit 1
fi
exit 0

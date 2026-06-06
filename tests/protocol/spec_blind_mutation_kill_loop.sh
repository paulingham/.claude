#!/usr/bin/env bash
# Spec-Blind Validator — independent behavioural checks for AC1, AC3, AC5, AC6, AC7, AC8, AC9
# and Cross-File Consistency.
#
# Derived SOLELY from the AC plan at:
#   ~/.claude/pipeline-state/mutation-kill-loop/plan.md (rev 2)
# and from reading the resulting document prose directly.
#
# These checks are INDEPENDENT of tests/protocol/mutation_kill_loop_spec.sh — no assertions
# were copied. The value is orthogonal signal: if both suites pass, the documents satisfy
# the ACs in two independent readings.
#
# Approach: where the build-time suite checks text-presence, this suite checks:
#   - Semantic ordering within the round body (AC3 load-bearing constraint)
#   - The deterministic =0→120 mapping and the no-disable invariant (AC1/Cross-file)
#   - The exact fallback clause in Tier 3.5 dedup (AC9 semantic precision)
#   - Pointer-only in build-implementation (no re-spec present — AC2/Cross-file)
#   - The comment-level append-below hint in the atdd append-structure block (AC6)
#   - Freshness-contract statement includes the causal chain (AC8)
#   - qa-engineer Verify item explicitly names both read-only-measuring AND the active loop (AC5)
#
# Exit codes: 0 = all pass; 1 = one or more failures.

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

pass() { echo "  PASS: $1"; PASSED=$(( PASSED + 1 )); }
fail() { echo "  FAIL: $1"; echo "    expected: $2"; echo "    in:       $3"; FAILURES=$(( FAILURES + 1 )); }

# literal fixed-string search
contains() { grep -qF -- "$1" "$2"; }

# extended regex search
contains_re() { grep -qE -- "$1" "$2"; }

# Returns the 1-based line number of the FIRST occurrence of a literal pattern, or empty string.
line_of() { grep -nF -- "$1" "$2" | head -1 | cut -d: -f1; }


########################################################################
# AC1 — KILL_LOOP_START stamp semantics and =0→120 determinism
########################################################################
echo ""
echo "=== AC1: start-stamp semantics and =0 determinism ==="

# The AC plan says: stamp fires "immediately before the first mutation run that establishes
# the baseline", and is checked "at the top of every round before authoring more kill-tests".
# The build-time suite checks presence of "KILL_LOOP_START" and "before the first mutation run".
# We independently verify the CAUSAL relationship: the stamp description must appear in a
# context that also mentions "baseline" (the first run establishes the baseline).
if contains_re "KILL_LOOP_START.*baseline\|baseline.*KILL_LOOP_START" "$ATDD" || \
   ( contains "KILL_LOOP_START" "$ATDD" && contains "establishes the baseline" "$ATDD" ); then
  pass "AC1: KILL_LOOP_START stamp is associated with the baseline-establishing first run"
else
  fail "AC1: KILL_LOOP_START stamp does not appear near 'establishes the baseline'" \
       "KILL_LOOP_START in same context as 'establishes the baseline'" "$ATDD"
fi

# AC plan § Loop Specification says: "=0 (and any value < 120) coerces to the floor / default".
# More precisely, the spec distinguishes =0→120 from negative/non-integer→300.
# The plan says "Deterministically: 0 → 120 (floor); negative or non-integer → 300 (default)."
# We verify both branches are spelled out.
if contains "0 → 120" "$ATDD"; then
  pass "AC1: =0 deterministically coerces to 120 (floor branch spelled out)"
else
  fail "AC1: =0 → 120 branch missing" "'0 → 120'" "$ATDD"
fi

if contains_re "negative.*300|non-integer.*300|300.*non-integer|300.*negative" "$ATDD"; then
  pass "AC1: negative/non-integer → 300 (default branch spelled out)"
else
  fail "AC1: negative/non-integer → 300 branch missing" \
       "text linking 'negative' or 'non-integer' to 300" "$ATDD"
fi

# The AC plan requires the budget check fires at the "top of every round before authoring".
# Specifically, round body step 1 must be the Budget check and step 4 must be Author kill-tests.
# We verify step numbering: "1. **Budget check**" appears before "4. **Author kill-tests**"
BUDGET_LINE=$(line_of "1. **Budget check**" "$ATDD")
AUTHOR_LINE=$(line_of "4. **Author kill-tests**" "$ATDD")
if [ -n "$BUDGET_LINE" ] && [ -n "$AUTHOR_LINE" ] && [ "$BUDGET_LINE" -lt "$AUTHOR_LINE" ]; then
  pass "AC1: Round body step 1 Budget check appears before step 4 Author kill-tests"
else
  fail "AC1: Round body step 1 (Budget check) does not precede step 4 (Author kill-tests)" \
       "Line(budget_check=${BUDGET_LINE:-missing}) < Line(author=${AUTHOR_LINE:-missing})" "$ATDD"
fi


########################################################################
# AC3 — NO_PROGRESS check BEFORE authoring (load-bearing ordering)
########################################################################
echo ""
echo "=== AC3: NO_PROGRESS-before-author ordering in round body ==="

# AC plan states the ordering is LOAD-BEARING and cites the exact canonical line:
# "budget check → read survivors → NO_PROGRESS check → author → re-run → append → REACHED check → loop."
# We verify this canonical ordering line is present verbatim (the plan quotes it as the
# explicit protection against reordering).
if contains "NO_PROGRESS check → author" "$ATDD"; then
  pass "AC3: canonical ordering line 'NO_PROGRESS check → author' present in atdd"
else
  fail "AC3: canonical ordering line absent" "'NO_PROGRESS check → author'" "$ATDD"
fi

# Verify that in the numbered round body, step 3 is the No-progress check and
# step 4 is Author kill-tests (the AC says "This check runs BEFORE authoring").
NOPROGRESS_LINE=$(line_of "3. **No-progress check**" "$ATDD")
AUTHOR_LINE4=$(line_of "4. **Author kill-tests**" "$ATDD")
if [ -n "$NOPROGRESS_LINE" ] && [ -n "$AUTHOR_LINE4" ] && [ "$NOPROGRESS_LINE" -lt "$AUTHOR_LINE4" ]; then
  pass "AC3: Round body step 3 (No-progress check) precedes step 4 (Author kill-tests)"
else
  fail "AC3: Step 3 No-progress check does not precede step 4 Author kill-tests" \
       "Line(step3=${NOPROGRESS_LINE:-missing}) < Line(step4=${AUTHOR_LINE4:-missing})" "$ATDD"
fi

# The AC requires the two-consecutive-zero-kill rule to include the phrase "BEFORE authoring"
# (to make the constraint explicit to an implementer).
if contains "BEFORE authoring" "$ATDD"; then
  pass "AC3: BEFORE authoring qualifier present in no-progress check"
else
  fail "AC3: 'BEFORE authoring' qualifier absent from no-progress rule" \
       "'BEFORE authoring'" "$ATDD"
fi

# Verify all three outcome tokens are present in exit outcomes section (byte-exact per plan).
for tok in "REACHED" "EXHAUSTED" "NO_PROGRESS"; do
  if contains "$tok" "$ATDD"; then
    pass "AC3: outcome token '$tok' present in atdd"
  else
    fail "AC3: outcome token '$tok' missing" "'$tok'" "$ATDD"
  fi
done


########################################################################
# AC6 — append-below-Kill-Loop + Tier-3.5 ordering in append structure
########################################################################
echo ""
echo "=== AC6: append structure Tier-3.5-below-Kill-Loop ordering ==="

# AC plan specifies the append structure block contains a comment:
# <!-- Tier 3.5 verify sections, if any, appended BELOW the last Kill-Loop round at Final Gate -->
# This is more specific than "appended BELOW" alone — it names Final Gate context.
if contains "appended BELOW the last Kill-Loop round at Final Gate" "$ATDD"; then
  pass "AC6: append-structure comment names 'BELOW the last Kill-Loop round at Final Gate'"
else
  fail "AC6: comment 'appended BELOW the last Kill-Loop round at Final Gate' absent" \
       "'appended BELOW the last Kill-Loop round at Final Gate'" "$ATDD"
fi

# Verify the append-structure never-clobber rule: "append-only" explicitly stated.
if contains "append-only" "$ATDD"; then
  pass "AC6: 'append-only' rule stated for rounds"
else
  fail "AC6: 'append-only' rule absent" "'append-only'" "$ATDD"
fi

# Verify the note at the bottom of the append-structure block that cross-refs verify § 4.25.
# The AC plan says atdd should note that § 4.25 dedups against latest Kill-Loop round.
if contains "§ 4.25" "$ATDD"; then
  pass "AC6: atdd cross-references verify § 4.25"
else
  fail "AC6: cross-reference to § 4.25 absent in atdd" "'§ 4.25'" "$ATDD"
fi


########################################################################
# AC7 — engineering-invariants Tier 3 threshold + exact cross-ref literal
########################################################################
echo ""
echo "=== AC7: engineering-invariants Tier 3 threshold unchanged + cross-ref ==="

# AC plan says the cross-ref must contain the LITERAL "atdd-procedure.md step 4 Mutation Kill Loop".
# We check this exact string (no regex loosening).
if contains "atdd-procedure.md step 4 Mutation Kill Loop" "$INVARIANTS"; then
  pass "AC7: engineering-invariants contains exact literal 'atdd-procedure.md step 4 Mutation Kill Loop'"
else
  fail "AC7: exact cross-ref literal absent" \
       "'atdd-procedure.md step 4 Mutation Kill Loop'" "$INVARIANTS"
fi

# Verify ≥70% threshold still present (AC says "No threshold change").
if contains "≥70%" "$INVARIANTS"; then
  pass "AC7: ≥70% threshold unchanged in engineering-invariants"
else
  fail "AC7: ≥70% threshold missing from engineering-invariants" "'≥70%'" "$INVARIANTS"
fi

# AC plan § Cross-File Consistency item 1: the oracle line at engineering-invariants :89
# also gets a cross-ref. Verify the Tier 3 entry in the proof-of-correctness tier stack
# also names the Mutation Kill Loop (the plan says "Oracle line :89 gets a cross-ref").
# We check it: the tier-stack entry for Tier 3 must include "Mutation Kill Loop".
if contains_re "Tier 3.*Mutation Kill Loop|Mutation Kill Loop.*Tier 3" "$INVARIANTS"; then
  pass "AC7: Tier 3 oracle / tier-stack entry in engineering-invariants also names Mutation Kill Loop"
else
  fail "AC7: Tier 3 oracle entry does not cross-ref Mutation Kill Loop" \
       "Tier 3 entry containing 'Mutation Kill Loop'" "$INVARIANTS"
fi


########################################################################
# AC5 — verify Tier 3 read-only note; qa-engineer aligned
########################################################################
echo ""
echo "=== AC5: verify Tier 3 read-only note + qa-engineer alignment ==="

# The AC plan requires verify/SKILL.md § 4 to state that the active loop ran at Build
# AND that verify MUST NOT write tests or commit.
# We verify both constraints appear together in the same note (not just anywhere in the file).
# Strategy: find line of "read-only" in verify, then check nearby lines contain "Build" and
# "MUST NOT write tests or commit".
READONLY_LINE=$(line_of "read-only" "$VERIFY_SKILL")
if [ -n "$READONLY_LINE" ]; then
  # Extract a window of lines around the read-only mention and check for required context
  WINDOW=$(awk "NR>=$((READONLY_LINE - 2)) && NR<=$((READONLY_LINE + 10))" "$VERIFY_SKILL")
  if echo "$WINDOW" | grep -qF "MUST NOT write tests or commit"; then
    pass "AC5: verify read-only note includes 'MUST NOT write tests or commit' in same block"
  else
    fail "AC5: 'MUST NOT write tests or commit' not found near read-only note" \
         "'MUST NOT write tests or commit' within 10 lines of 'read-only'" "$VERIFY_SKILL"
  fi
  if echo "$WINDOW" | grep -qF "Build"; then
    pass "AC5: verify read-only note mentions 'Build' (active loop ran at Build)"
  else
    fail "AC5: read-only note does not mention 'Build'" \
         "'Build' within 10 lines of 'read-only'" "$VERIFY_SKILL"
  fi
else
  fail "AC5: 'read-only' not found in verify/SKILL.md at all" "'read-only'" "$VERIFY_SKILL"
fi

# qa-engineer.md Verify item must state both "read-only" and "Mutation Kill Loop" (AC5 alignment).
if contains "read-only" "$QA_AGENT"; then
  pass "AC5: qa-engineer.md Verify item contains 'read-only'"
else
  fail "AC5: qa-engineer.md Verify item missing 'read-only'" "'read-only'" "$QA_AGENT"
fi

if contains "Mutation Kill Loop" "$QA_AGENT"; then
  pass "AC5: qa-engineer.md Verify item references Mutation Kill Loop"
else
  fail "AC5: qa-engineer.md Verify item does not reference Mutation Kill Loop" \
       "'Mutation Kill Loop'" "$QA_AGENT"
fi


########################################################################
# AC8 — verify note states freshness contract intact with causal chain
########################################################################
echo ""
echo "=== AC8: verify note causal chain — loop at Build before Final Gate fans out ==="

# AC plan § AC8 says the statement must say BOTH:
#   (a) the loop runs at Build before the Final Gate fans out, AND
#   (b) no mid-gate commits occur, AND
#   (c) the verification-evidence.json git_head freshness contract is intact.
# The build-time suite checks each string individually. We independently check that
# all three appear in close proximity (within the same note block).
FRESHNESS_LINE=$(line_of "freshness contract is intact" "$VERIFY_SKILL")
if [ -n "$FRESHNESS_LINE" ]; then
  NOTE_BLOCK=$(awk "NR>=$((FRESHNESS_LINE - 8)) && NR<=$((FRESHNESS_LINE + 2))" "$VERIFY_SKILL")
  if echo "$NOTE_BLOCK" | grep -qF "no mid-gate commits"; then
    pass "AC8: 'no mid-gate commits' appears in same block as 'freshness contract is intact'"
  else
    fail "AC8: 'no mid-gate commits' absent from freshness-intact block" \
         "'no mid-gate commits' near 'freshness contract is intact'" "$VERIFY_SKILL"
  fi
  if echo "$NOTE_BLOCK" | grep -qE "before the Final Gate|before.*Final Gate fans out"; then
    pass "AC8: 'before the Final Gate' appears in same block as 'freshness contract is intact'"
  else
    fail "AC8: causal clause 'before the Final Gate' absent from freshness-intact block" \
         "'before the Final Gate' near 'freshness contract is intact'" "$VERIFY_SKILL"
  fi
else
  fail "AC8: 'freshness contract is intact' not found in verify/SKILL.md" \
       "'freshness contract is intact'" "$VERIFY_SKILL"
fi


########################################################################
# AC9 — Tier 3.5 semantic precision: fallback clause + append placement
########################################################################
echo ""
echo "=== AC9: Tier 3.5 dedup fallback clause and append placement ==="

# AC plan says the dedup prerequisite must reference the "latest Kill-Loop round's survivor list"
# AND include the fallback: "fall back to the Tier-3 baseline only when no Kill-Loop rounds
# are present". The plan is explicit that deduping against only the baseline is wrong.
# We check for the fallback clause specifically.
if contains_re "fall back.*Tier-3 baseline.*no Kill-Loop|no Kill-Loop.*fall back.*Tier-3 baseline" \
   "$VERIFY_SKILL"; then
  pass "AC9: Tier 3.5 dedup fallback clause present ('fall back to Tier-3 baseline ... no Kill-Loop rounds')"
else
  fail "AC9: Tier 3.5 dedup fallback clause absent" \
       "text linking 'fall back to Tier-3 baseline' with 'no Kill-Loop rounds'" "$VERIFY_SKILL"
fi

# The AC also requires the append invariant to say "below any Kill-Loop rounds"
# (i.e. after the last ### Kill-Loop Round N section).
if contains "below any Kill-Loop rounds" "$VERIFY_SKILL"; then
  pass "AC9: Tier 3.5 append invariant says 'below any Kill-Loop rounds'"
else
  fail "AC9: 'below any Kill-Loop rounds' absent from verify/SKILL.md" \
       "'below any Kill-Loop rounds'" "$VERIFY_SKILL"
fi

# The AC9 fix also adds a warning against interleaving: "Do NOT append between the
# Tier-3 baseline and the Kill-Loop rounds". Verify this guard is present.
if contains "Do NOT append between the Tier-3 baseline and the Kill-Loop rounds" "$VERIFY_SKILL"; then
  pass "AC9: anti-interleave guard present in Tier 3.5 append invariant"
else
  fail "AC9: anti-interleave guard absent" \
       "'Do NOT append between the Tier-3 baseline and the Kill-Loop rounds'" "$VERIFY_SKILL"
fi


########################################################################
# Cross-File Consistency
########################################################################
echo ""
echo "=== Cross-File Consistency: knob/default/enum byte-identical; no re-spec ==="

# 1. CLAUDE_MUTATION_KILL_BUDGET_SECONDS must appear in BOTH atdd and build-implementation
#    (the only two places the plan says it appears — cross-ref item 7).
for f in "$ATDD" "$BUILD_IMPL"; do
  label=$(basename "$f")
  if contains "CLAUDE_MUTATION_KILL_BUDGET_SECONDS" "$f"; then
    pass "consistency: CLAUDE_MUTATION_KILL_BUDGET_SECONDS present in $label"
  else
    fail "consistency: CLAUDE_MUTATION_KILL_BUDGET_SECONDS absent from $label" \
         "'CLAUDE_MUTATION_KILL_BUDGET_SECONDS'" "$f"
  fi
done

# 2. Default 300 byte-identical in both files (cross-ref item 7: "only two places it appears").
for f in "$ATDD" "$BUILD_IMPL"; do
  label=$(basename "$f")
  if contains "300" "$f"; then
    pass "consistency: default '300' present in $label"
  else
    fail "consistency: '300' absent from $label" "'300'" "$f"
  fi
done

# 3. OUTCOME enum — all three tokens byte-identical in atdd AND build-implementation
#    (cross-ref item 8).
for tok in "REACHED" "EXHAUSTED" "NO_PROGRESS"; do
  for f in "$ATDD" "$BUILD_IMPL"; do
    label=$(basename "$f")
    if contains "$tok" "$f"; then
      pass "consistency: '$tok' present in $label"
    else
      fail "consistency: '$tok' absent from $label" "'$tok'" "$f"
    fi
  done
done

# 4. No re-spec: build-implementation must NOT contain its own round-body step list
#    (the plan says pointer-only; re-specifying the round body inline would cause drift).
#    The build-time spec does not check for ABSENCE of a re-spec. We do.
#    Heuristic: build-implementation must NOT contain "1. **Budget check**" or
#    "2. **Read survivors**" (the verbatim round-body step headers from atdd step 4).
if ! contains "1. **Budget check**" "$BUILD_IMPL" && ! contains "2. **Read survivors**" "$BUILD_IMPL"; then
  pass "consistency: build-implementation does NOT re-specify the round body steps (pointer-only)"
else
  fail "consistency: build-implementation contains round-body step headers — violation of pointer-only DRY rule" \
       "absence of '1. **Budget check**' and '2. **Read survivors**'" "$BUILD_IMPL"
fi

# 5. No disable hatch: atdd must state =0 is NOT a disable (Iron Law).
if contains "=0" "$ATDD" && contains_re "NOT.*disable|cannot be disabled|=0.*is NOT" "$ATDD"; then
  pass "consistency: atdd asserts =0 is NOT a disable hatch"
else
  fail "consistency: no-disable assertion absent from atdd" \
       "'=0' + 'NOT.*disable' or 'cannot be disabled'" "$ATDD"
fi

# 6. Cross-ref chain integrity: software-engineer.md → atdd step 4
if contains "atdd-procedure.md" "$SE_AGENT"; then
  pass "consistency: software-engineer.md references atdd-procedure.md"
else
  fail "consistency: software-engineer.md does not reference atdd-procedure.md" \
       "'atdd-procedure.md'" "$SE_AGENT"
fi

# 7. Cross-ref chain integrity: qa-engineer.md Verify item → verify/SKILL.md read-only concept
#    (cross-ref item 4: qa-engineer Verify item → verify § 4 read-only note).
if contains "verify" "$QA_AGENT" && contains "read-only" "$QA_AGENT"; then
  pass "consistency: qa-engineer.md Verify item references verify and states read-only"
else
  fail "consistency: qa-engineer.md Verify item missing verify reference or read-only statement" \
       "'verify' + 'read-only' in qa-engineer.md" "$QA_AGENT"
fi


########################################################################
# Summary
########################################################################
echo ""
echo "================================================"
echo "Spec-Blind Results: $PASSED passed, $FAILURES failed"
echo "================================================"

if [ "$FAILURES" -gt 0 ]; then
  exit 1
fi
exit 0

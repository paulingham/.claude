#!/usr/bin/env bash
# AC5 — `### Step 2d: DOM Smoke` header positioned between the prior `### Step
# 2*` header and `### Step 3` in skills/build-implementation/SKILL.md.
#
# AC5-as-written says "between Step 2c and Step 3", but the SKILL has no Step
# 2c — the existing sequence is `Step 2 → Step 2b → Step 3`. Author of plan
# v2 conflated the latest 2x letter. The AC intent is "2d goes after the last
# 2x step and before Step 3". This test asserts that invariant against the
# actual prior Step 2 letter (currently 2b).
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"

PASS=0; FAIL=0

assert() {
  local label=$1; shift
  if "$@"; then echo "  ok: $label"; PASS=$((PASS + 1))
  else echo "  FAIL: $label"; FAIL=$((FAIL + 1)); fi
}

echo "Test step_2d_between_prior_step2_and_step3"

LINE_2B=$(grep -n '^### Step 2b' "$SKILL" | head -1 | cut -d: -f1)
LINE_2D=$(grep -n '^### Step 2d: DOM Smoke' "$SKILL" | head -1 | cut -d: -f1)
LINE_3=$(grep -n '^### Step 3: Shape Check' "$SKILL" | head -1 | cut -d: -f1)

assert "### Step 2b header present (prior step)" test -n "$LINE_2B"
assert "### Step 2d: DOM Smoke header present" test -n "$LINE_2D"
assert "### Step 3 header present" test -n "$LINE_3"

if [[ -n "$LINE_2B" && -n "$LINE_2D" && -n "$LINE_3" ]]; then
  assert "Step 2b precedes Step 2d" test "$LINE_2B" -lt "$LINE_2D"
  assert "Step 2d precedes Step 3" test "$LINE_2D" -lt "$LINE_3"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

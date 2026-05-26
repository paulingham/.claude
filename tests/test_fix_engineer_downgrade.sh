#!/usr/bin/env bash
# Structural fixture test for AC5: fix-engineer Opus-to-Sonnet downgrade clause.
# Greps build-implementation/SKILL.md Step 5 for the exact canonical phrase
# mandated by plan-validation Finding 3: "Round 3: downgrade to Sonnet"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"
FIX_ENGINEER="$REPO_ROOT/agents/fix-engineer.md"

assert_grep() {
  local pattern="$1" file="$2" label="$3"
  if grep -q "$pattern" "$file"; then
    echo "PASS: $label"
  else
    echo "FAIL: $label (pattern '$pattern' not found in $file)" >&2
    exit 1
  fi
}

# AC5 canonical phrase (exact string mandated by plan-validation Finding 3)
assert_grep "Round 3: downgrade to Sonnet" "$SKILL" \
  "build_step5_contains_round3_downgrade_clause"

# AC5 fix-engineer downgrade contract section present
assert_grep "Downgrade Contract" "$FIX_ENGINEER" \
  "fix_engineer_contains_downgrade_contract_section"

echo "ALL TESTS PASSED"

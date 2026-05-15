#!/usr/bin/env bash
# Slice A — adopt-udiff-assertflip: byte-pin contract tests for the
# build-implementation skill. Asserts Step 2.5 (Edit Format) prescribes
# unified-diff via `git apply --check`, forbids `...` placeholders, and
# the Step 2/2b byte-pin "cap reduces from 5 to 3" is unchanged.
set -euo pipefail

CLAUDE_HOME="${CLAUDE_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

PASS=0; FAIL=0

report_pass() { echo "PASS: $1"; PASS=$((PASS + 1)); }
report_fail() { echo "FAIL: $1 — $2" >&2; FAIL=$((FAIL + 1)); }

grep_file() {
  local label=$1 file=$2 needle=$3
  if grep -qF -- "$needle" "$file"; then
    report_pass "$label"
  else
    report_fail "$label" "expected literal '$needle' in $file"
  fi
}

SKILL="$CLAUDE_HOME/skills/build-implementation/SKILL.md"

# test_build_skill_step_2_5_present
grep_file "test_build_skill_step_2_5_present" "$SKILL" 'Step 2.5'

# test_skill_names_git_apply_check
grep_file "test_skill_names_git_apply_check" "$SKILL" 'git apply --check'

# test_skill_forbids_ellipsis_in_diffs
grep_file "test_skill_forbids_ellipsis_in_diffs" "$SKILL" 'MUST NOT contain `...`'

# test_byte_pin_cap_reduces_unchanged (regression guard)
grep_file "test_byte_pin_cap_reduces_unchanged" "$SKILL" 'cap reduces from 5 to 3'

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

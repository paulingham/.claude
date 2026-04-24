#!/usr/bin/env bash
# Skill-shell contract tests for /internal-eval (Story 2).
# Validates SKILL.md presence, verdict table, entry commands, sub-skills, and CLAUDE.md row.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLAUDE_MD="$(cd "${SKILL_ROOT}/../.." && pwd)/CLAUDE.md"
SKILL_MD="${SKILL_ROOT}/SKILL.md"
PASS=0; FAIL=0

record() {
  [ "$1" = "ok" ] && { echo "PASS: $2"; PASS=$((PASS + 1)); return; }
  echo "FAIL: $2" >&2; FAIL=$((FAIL + 1))
}

assert_file() { [ -f "$1" ] && record ok "$2" || record fail "$2 (missing: $1)"; }
assert_grep() { grep -qF "$2" "$1" 2>/dev/null && record ok "$3" || record fail "$3 (needle absent: $2)"; }

check_verdicts() {
  for v in EVAL_PASSED EVAL_FAILED EVAL_BASELINE_CAPTURED INSUFFICIENT_CASES; do
    assert_grep "$SKILL_MD" "$v" "SKILL.md declares verdict $v"
  done
}

check_commands() {
  for c in "/internal-eval run" "/internal-eval capture backfill" "/internal-eval capture promote" "/internal-eval inspect"; do
    assert_grep "$SKILL_MD" "$c" "SKILL.md documents entry command: $c"
  done
}

check_sub_skills() {
  for sub in capture run score; do
    assert_file "${SKILL_ROOT}/${sub}/SKILL.md" "sub-skill stub ${sub}/SKILL.md exists"
  done
}

main() {
  assert_file "$SKILL_MD" "skills/internal-eval/SKILL.md exists"
  check_verdicts; check_commands; check_sub_skills
  assert_grep "$CLAUDE_MD" "/internal-eval" "CLAUDE.md Skill Directory contains /internal-eval row"
  echo "---"; echo "Passed: ${PASS}  Failed: ${FAIL}"
  [ "$FAIL" -eq 0 ]
}

main "$@"

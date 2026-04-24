#!/usr/bin/env bash
# Story 12 — README + CLAUDE.md wiring for /internal-eval (section header,
# run-suite pointer, baselines path, privacy gate, 80% methodology note).
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
README="${ROOT}/README.md"
CLAUDE_MD="${ROOT}/CLAUDE.md"
PASS=0; FAIL=0

record() {
  [ "$1" = "ok" ] && { echo "PASS: $2"; PASS=$((PASS + 1)); return; }
  echo "FAIL: $2" >&2; FAIL=$((FAIL + 1))
}

assert_grep() { grep -qF "$2" "$1" 2>/dev/null && record ok "$3" || record fail "$3"; }
assert_rx()   { grep -qE "$2" "$1" 2>/dev/null && record ok "$3" || record fail "$3"; }

main() {
  assert_grep "$README" "## Internal Evaluation" "README has Internal Evaluation section"
  assert_grep "$README" "run-suite.sh" "README mentions run-suite.sh"
  assert_grep "$README" "eval/baselines/" "README mentions eval/baselines/"
  assert_rx   "$README" "\.privacy-acked|CLAUDE_EVAL_CAPTURE_ACKED" "README mentions privacy gate"
  assert_grep "$README" "80% claim" "README references 80% methodology"
  assert_rx   "$CLAUDE_MD" "80% claim.*eval/baselines" "CLAUDE.md has 80% claim note"
  echo "---"; echo "Passed: ${PASS}  Failed: ${FAIL}"
  [ "$FAIL" -eq 0 ]
}

main "$@"

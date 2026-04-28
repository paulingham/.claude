#!/usr/bin/env bash
# Tests for hooks/tdd-guard.sh PR-creation gate (ATDD enforcement).
# Uses TDD_GUARD_DIFF_FIXTURE env var to inject a fake diff line list.

set -uo pipefail

HOOK="$(dirname "$0")/../hooks/tdd-guard.sh"
PASS=0
FAIL=0

_run_hook() {
  local cmd="$1" diff="$2" base="${3:-}"
  local input output rc
  input=$(printf %s "$cmd" | jq -Rsc '{tool_input:{command:.}}')
  if [[ -n "$base" ]]; then
    output=$(TDD_GUARD_DIFF_FIXTURE="$diff" GITHUB_BASE_REF="$base" bash "$HOOK" <<< "$input" 2>&1)
  else
    output=$(TDD_GUARD_DIFF_FIXTURE="$diff" bash "$HOOK" <<< "$input" 2>&1)
  fi
  rc=$?
  echo "$rc|$output"
}

_assert_blocked() {
  local name="$1" result="$2"
  if [[ "${result%%|*}" == "1" ]] && echo "${result#*|}" | grep -q 'block'; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name | $result"; FAIL=$((FAIL+1))
  fi
}

_assert_allowed() {
  local name="$1" result="$2"
  if [[ "${result%%|*}" == "0" ]]; then
    echo "PASS: $name"; PASS=$((PASS+1))
  else
    echo "FAIL: $name | $result"; FAIL=$((FAIL+1))
  fi
}

# 1. Source-only diff blocks pr-create
r=$(_run_hook 'gh pr create --title x' $'src/foo.ts\nlib/bar.py')
_assert_blocked "source-only diff blocks pr create" "$r"

# 2. Source + test diff allows pr-create
r=$(_run_hook 'gh pr create --title x' $'src/foo.ts\ntests/test_foo.ts')
_assert_allowed "source + test diff allows pr create" "$r"

# 3. Test-only diff allows pr-create
r=$(_run_hook 'gh pr create' $'tests/test_foo.ts\ntests/test_bar.py')
_assert_allowed "test-only diff allows pr create" "$r"

# 4. Exempt-only diff allows pr-create
r=$(_run_hook 'gh pr create' $'README.md\npackage.json\nhooks/foo.sh')
_assert_allowed "exempt-only diff allows pr create" "$r"

# 5. gh pr ready triggers gate same as pr create
r=$(_run_hook 'gh pr ready 42' 'src/foo.ts')
_assert_blocked "gh pr ready triggers gate" "$r"

# 6. Non-PR commands pass through
r=$(_run_hook 'ls -la' 'src/foo.ts')
_assert_allowed "non-PR command passes through" "$r"
r=$(_run_hook 'echo hi' 'lib/bar.py')
_assert_allowed "echo command passes through" "$r"

# 7. Python test_*.py path classified as test
r=$(_run_hook 'gh pr create' $'src/foo.py\ntests/test_foo.py')
_assert_allowed "test_*.py classified as test" "$r"
r=$(_run_hook 'gh pr create' $'lib/bar.py\nlib/test_bar.py')
_assert_allowed "lib/test_bar.py classified as test" "$r"

# 8. GITHUB_BASE_REF override is honored (still blocks on source-only)
r=$(_run_hook 'gh pr create' 'src/foo.ts' 'develop')
_assert_blocked "GITHUB_BASE_REF=develop honored" "$r"
if echo "${r#*|}" | grep -q "develop"; then
  echo "PASS: block message references custom base develop"; PASS=$((PASS+1))
else
  echo "FAIL: base ref not in message | $r"; FAIL=$((FAIL+1))
fi

echo
echo "RESULTS: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

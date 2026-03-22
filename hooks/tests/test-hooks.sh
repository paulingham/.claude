#!/usr/bin/env bash
# Hook Test Harness — tests all Claude Code hooks with representative inputs
# Run from ~/.claude/: bash hooks/tests/test-hooks.sh
# Exit 0 if all pass, exit 1 if any fail.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

run_test() {
  local name="$1"
  local expected_exit="$2"
  local actual_exit="$3"
  if [[ "$actual_exit" -eq "$expected_exit" ]]; then
    pass "$name"
  else
    fail "$name" "$expected_exit" "$actual_exit"
  fi
}

echo "=== Hook Test Harness ==="
echo ""

# -- hook-profile tests ------------------------------------------------------
echo "-- hook-profile.sh --"

source "$HOOKS_DIR/hook-profile.sh"

CLAUDE_HOOK_PROFILE=minimal check_hook_profile "minimal"
run_test "profile=minimal, required=minimal -> allow" 0 $?

CLAUDE_HOOK_PROFILE=minimal check_hook_profile "standard"
run_test "profile=minimal, required=standard -> skip" 1 $?

CLAUDE_HOOK_PROFILE=standard check_hook_profile "standard"
run_test "profile=standard, required=standard -> allow" 0 $?

CLAUDE_HOOK_PROFILE=strict check_hook_profile "standard"
run_test "profile=strict, required=standard -> allow" 0 $?

unset CLAUDE_HOOK_PROFILE
check_hook_profile "standard"
run_test "profile=unset (default=standard), required=standard -> allow" 0 $?

echo ""

# -- loop-guard tests --------------------------------------------------------
echo "-- loop-guard.sh --"

source "$HOOKS_DIR/loop-guard.sh"

# Clear any existing guard file for test isolation
rm -f "/tmp/claude-hook-guard/test-loop-guard-hook"

LOOP_FAILED=false
for i in $(seq 1 11); do
  check_loop_guard "test-loop-guard-hook" 10 60
  exit_code=$?
  if [[ $i -le 10 && $exit_code -ne 0 ]]; then
    fail "loop-guard call $i of 10 (within limit)" 0 $exit_code
    LOOP_FAILED=true
    break
  elif [[ $i -eq 11 && $exit_code -ne 1 ]]; then
    fail "loop-guard call 11 (over limit) should return 1" 1 $exit_code
    LOOP_FAILED=true
    break
  fi
done
if [[ "$LOOP_FAILED" == "false" ]]; then
  pass "loop-guard: 10 calls allowed, 11th blocked"
fi

echo ""

# -- orchestrator-discipline tests -------------------------------------------
echo "-- orchestrator-discipline.sh --"

CLAUDE_FILE_PATH="src/foo.ts" bash "$HOOKS_DIR/orchestrator-discipline.sh" > /dev/null 2>&1
run_test "orchestrator-discipline: .ts file -> block (exit 2)" 2 $?

CLAUDE_FILE_PATH="rules/foo.md" bash "$HOOKS_DIR/orchestrator-discipline.sh" > /dev/null 2>&1
run_test "orchestrator-discipline: .md file -> allow (exit 0)" 0 $?

CLAUDE_FILE_PATH="" bash "$HOOKS_DIR/orchestrator-discipline.sh" > /dev/null 2>&1
run_test "orchestrator-discipline: empty path -> allow (exit 0)" 0 $?

echo ""

# -- tdd-guard tests ---------------------------------------------------------
echo "-- tdd-guard.sh --"

# Non-source file -> allow
CLAUDE_FILE_PATH="README.md" bash "$HOOKS_DIR/tdd-guard.sh" < /dev/null > /dev/null 2>&1
run_test "tdd-guard: README.md -> allow (exit 0)" 0 $?

# Empty path -> allow
CLAUDE_FILE_PATH="" bash "$HOOKS_DIR/tdd-guard.sh" < /dev/null > /dev/null 2>&1
run_test "tdd-guard: empty path -> allow (exit 0)" 0 $?

# Test file -> allow
CLAUDE_FILE_PATH="src/foo.test.ts" bash "$HOOKS_DIR/tdd-guard.sh" < /dev/null > /dev/null 2>&1
run_test "tdd-guard: test file -> allow (exit 0)" 0 $?

# New source file (doesn't exist) -> allow (greenfield)
CLAUDE_FILE_PATH="/tmp/nonexistent-source-$(date +%s).ts" bash "$HOOKS_DIR/tdd-guard.sh" < /dev/null > /dev/null 2>&1
run_test "tdd-guard: new source file (not on disk) -> allow (exit 0)" 0 $?

echo ""

# -- auto-pr tests -----------------------------------------------------------
echo "-- auto-pr.sh --"

# On main -> skip
(cd /tmp && git init -q test-auto-pr-$$ 2>/dev/null && cd test-auto-pr-$$ && \
  git checkout -q -b main 2>/dev/null || true && \
  echo '{"stop_hook_active": false}' | BRANCH=main bash "$HOOKS_DIR/auto-pr.sh" > /dev/null 2>&1)
run_test "auto-pr: on main branch -> skip (exit 0)" 0 $?

# No upstream commits -> skip
echo '{"stop_hook_active": false}' | BRANCH=feature/test bash "$HOOKS_DIR/auto-pr.sh" > /dev/null 2>&1
run_test "auto-pr: advisory hook always exits 0" 0 $?

echo ""

# -- Summary -----------------------------------------------------------------
echo "=== Results: $PASS passed, $FAIL failed ==="
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo "Some tests failed. Review hook implementations."
  exit 1
fi

echo "All tests passed."
exit 0

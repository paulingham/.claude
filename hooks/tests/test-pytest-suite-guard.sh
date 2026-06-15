#!/usr/bin/env bash
# CI-BRIDGE: run by tests/shell/bridge_pytest_suite_guard.bats
# Tests for pytest-suite-guard.sh — a PreToolUse Bash hook.
# Blocks (exit 2) two command shapes that have hung/corrupted the pipeline:
#   RULE 1: unbounded whole-suite pytest (no scoping, no timeout).
#   RULE 2: worktree-reverting git op paired with pytest in one command string.
# Fails open (exit 0) on empty/garbage/non-Bash/unrelated commands.
#
# Run from ~/.claude/: bash hooks/tests/test-pytest-suite-guard.sh
# Exit 0 if all pass, exit 1 if any fail.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$HOOKS_DIR/pytest-suite-guard.sh"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

# Feed a Bash command string as JSON on stdin, assert exit code.
expect_cmd() {
  local name="$1" expected="$2" cmd="$3" actual
  jq -nc --arg c "$cmd" '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOK" > /dev/null 2>&1
  actual=$?
  if [[ "$actual" -eq "$expected" ]]; then pass "$name"; else fail "$name" "$expected" "$actual"; fi
}

# Feed raw stdin (not necessarily JSON), assert exit code.
expect_raw() {
  local name="$1" expected="$2" raw="$3" actual
  printf '%s' "$raw" | bash "$HOOK" > /dev/null 2>&1
  actual=$?
  if [[ "$actual" -eq "$expected" ]]; then pass "$name"; else fail "$name" "$expected" "$actual"; fi
}

# Feed a non-Bash tool payload, assert exit code.
expect_nonbash() {
  local name="$1" expected="$2" actual
  printf '%s' '{"tool_name":"Write","tool_input":{"file_path":"x.py"},"hook_event_name":"PreToolUse"}' \
    | bash "$HOOK" > /dev/null 2>&1
  actual=$?
  if [[ "$actual" -eq "$expected" ]]; then pass "$name"; else fail "$name" "$expected" "$actual"; fi
}

echo "=== pytest-suite-guard Test Harness ==="
echo ""

# -- fail-open / non-Bash ----------------------------------------------------
echo "-- fail-open --"
expect_raw "empty stdin -> allow (exit 0)" 0 ""
expect_raw "non-JSON garbage -> allow (exit 0)" 0 "this is not json {{{"
expect_nonbash "non-Bash tool payload -> allow (exit 0)" 0
expect_cmd "unrelated command ls -la -> allow (exit 0)" 0 "ls -la"
expect_cmd "word-boundary: mypytestthing -> allow (exit 0)" 0 "mypytestthing --run"
echo ""

# -- RULE 1: unbounded whole-suite pytest -> block ---------------------------
echo "-- RULE 1 blocks --"
expect_cmd "pytest tests/ -> block (exit 2)" 2 "pytest tests/"
expect_cmd "pytest tests -> block (exit 2)" 2 "pytest tests"
expect_cmd "pytest -q -> block (exit 2)" 2 "pytest -q"
expect_cmd "python -m pytest tests/ --tb=no -q -> block (exit 2)" 2 "python -m pytest tests/ --tb=no -q"
echo ""

# -- RULE 1: scoped / opted-out -> allow -------------------------------------
echo "-- RULE 1 allows --"
expect_cmd "pytest tests/test_foo.py -q -> allow (exit 0)" 0 "pytest tests/test_foo.py -q"
expect_cmd "pytest two named files + timeout -> allow (exit 0)" 0 "pytest tests/test_a.py tests/test_b.py --timeout=60"
expect_cmd "pytest -k router -> allow (exit 0)" 0 "pytest -k router"
expect_cmd "pytest -m 'not slow' -> allow (exit 0)" 0 "pytest -m 'not slow'"
expect_cmd "pytest --co -q -> allow (exit 0)" 0 "pytest --co -q"
expect_cmd "pytest --collect-only -> allow (exit 0)" 0 "pytest --collect-only"
expect_cmd "pytest --help -> allow (exit 0)" 0 "pytest --help"
expect_cmd "pytest -h -> allow (exit 0)" 0 "pytest -h"
expect_cmd "pytest named file no timeout -> allow (exit 0)" 0 "pytest tests/test_x.py"
expect_cmd "pytest --timeout only -> allow (exit 0)" 0 "pytest --timeout=60"
expect_cmd "pytest legacy *_test.py path -> allow (exit 0)" 0 "pytest tests/foo_test.py"
echo ""

# -- RULE 2: revert-then-pytest -> block -------------------------------------
echo "-- RULE 2 blocks --"
expect_cmd "git stash && pytest -> block (exit 2)" 2 "git stash && pytest tests/test_x.py"
expect_cmd "git checkout main -- tests/ && pytest -> block (exit 2)" 2 "git checkout main -- tests/ && pytest tests/"
expect_cmd "git stash; python -m pytest -> block (exit 2)" 2 "git stash; python -m pytest tests/test_y.py"
echo ""

# -- RULE 2: git ops without the pairing -> allow ----------------------------
echo "-- RULE 2 allows --"
expect_cmd "git checkout -b foo (no -- pathspec) -> allow (exit 0)" 0 "git checkout -b foo"
expect_cmd "git stash list (not push) -> allow (exit 0)" 0 "git stash list"
expect_cmd "git checkout main -- file, no pytest -> allow (exit 0)" 0 "git checkout main -- tests/test_a.py"
expect_cmd "git stash pop alone -> allow (exit 0)" 0 "git stash pop"
echo ""

echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then exit 1; fi
exit 0

#!/usr/bin/env bats
# CI bridge for hooks/tests/test-syntax-check.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-syntax-check harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-syntax-check.sh"; [ "$status" -eq 0 ]; }
@test "test-syntax-check reports 11 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-syntax-check.sh"; echo "$output" | grep -q "11 passed, 0 failed"; }

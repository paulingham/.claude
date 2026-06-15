#!/usr/bin/env bats
# CI bridge for hooks/tests/test-main-branch-guard.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-main-branch-guard harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-main-branch-guard.sh"; [ "$status" -eq 0 ]; }
@test "test-main-branch-guard reports 7 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-main-branch-guard.sh"; echo "$output" | grep -q "7 passed, 0 failed"; }

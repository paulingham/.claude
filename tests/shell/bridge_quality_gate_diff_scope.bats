#!/usr/bin/env bats
# CI bridge for hooks/tests/test-quality-gate-diff-scope.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-quality-gate-diff-scope harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-quality-gate-diff-scope.sh"; [ "$status" -eq 0 ]; }
@test "test-quality-gate-diff-scope reports 6/6 passed" { run bash "$REPO_ROOT/hooks/tests/test-quality-gate-diff-scope.sh"; echo "$output" | grep -q "6/6 passed"; }

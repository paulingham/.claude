#!/usr/bin/env bats
# CI bridge for hooks/tests/test-root-tree-clean-check.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-root-tree-clean-check harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-root-tree-clean-check.sh"; [ "$status" -eq 0 ]; }
@test "test-root-tree-clean-check reports 15 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-root-tree-clean-check.sh"; echo "$output" | grep -q "15 passed, 0 failed"; }

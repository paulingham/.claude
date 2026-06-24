#!/usr/bin/env bats
# CI bridge for hooks/tests/test-ab-compare.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-ab-compare harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-ab-compare.sh"; [ "$status" -eq 0 ]; }
@test "test-ab-compare reports 6 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-ab-compare.sh"; echo "$output" | grep -q "6 passed, 0 failed"; }

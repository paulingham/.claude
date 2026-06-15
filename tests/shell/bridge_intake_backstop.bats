#!/usr/bin/env bats
# CI bridge for hooks/tests/test-intake-backstop.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-intake-backstop harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-intake-backstop.sh"; [ "$status" -eq 0 ]; }
@test "test-intake-backstop reports 57 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-intake-backstop.sh"; echo "$output" | grep -q "57 passed, 0 failed"; }

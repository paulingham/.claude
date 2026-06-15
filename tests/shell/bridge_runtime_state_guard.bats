#!/usr/bin/env bats
# CI bridge for hooks/tests/test-runtime-state-guard.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-runtime-state-guard harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-runtime-state-guard.sh"; [ "$status" -eq 0 ]; }
@test "test-runtime-state-guard reports 30 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-runtime-state-guard.sh"; echo "$output" | grep -q "30 passed, 0 failed"; }

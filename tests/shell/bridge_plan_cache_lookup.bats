#!/usr/bin/env bats
# CI bridge for hooks/tests/test-plan-cache-lookup.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-plan-cache-lookup harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-plan-cache-lookup.sh"; [ "$status" -eq 0 ]; }
@test "test-plan-cache-lookup reports 5 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-plan-cache-lookup.sh"; echo "$output" | grep -q "5 passed, 0 failed"; }

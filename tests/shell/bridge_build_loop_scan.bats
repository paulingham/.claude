#!/usr/bin/env bats
# CI bridge for hooks/tests/test-build-loop-scan.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-build-loop-scan harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-build-loop-scan.sh"; [ "$status" -eq 0 ]; }
@test "test-build-loop-scan reports 30 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-build-loop-scan.sh"; echo "$output" | grep -q "30 passed, 0 failed"; }

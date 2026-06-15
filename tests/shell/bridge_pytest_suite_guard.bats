#!/usr/bin/env bats
# CI bridge for hooks/tests/test-pytest-suite-guard.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-pytest-suite-guard harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-pytest-suite-guard.sh"; [ "$status" -eq 0 ]; }
@test "test-pytest-suite-guard reports 27 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-pytest-suite-guard.sh"; echo "$output" | grep -q "27 passed, 0 failed"; }

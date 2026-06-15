#!/usr/bin/env bats
# CI bridge for hooks/tests/test-pipeline-entry-guard.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-pipeline-entry-guard harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-pipeline-entry-guard.sh"; [ "$status" -eq 0 ]; }
@test "test-pipeline-entry-guard reports 5 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-pipeline-entry-guard.sh"; echo "$output" | grep -q "5 passed, 0 failed"; }

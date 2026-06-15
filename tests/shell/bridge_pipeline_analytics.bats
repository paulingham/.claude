#!/usr/bin/env bats
# CI bridge for hooks/tests/test-pipeline-analytics.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-pipeline-analytics harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-pipeline-analytics.sh"; [ "$status" -eq 0 ]; }
@test "test-pipeline-analytics reports 5 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-pipeline-analytics.sh"; echo "$output" | grep -q "5 passed, 0 failed"; }

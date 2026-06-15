#!/usr/bin/env bats
# CI bridge for hooks/tests/test-detect-stale-pipeline-state.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-detect-stale-pipeline-state harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-detect-stale-pipeline-state.sh"; [ "$status" -eq 0 ]; }
@test "test-detect-stale-pipeline-state reports 6 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-detect-stale-pipeline-state.sh"; echo "$output" | grep -q "6 passed, 0 failed"; }

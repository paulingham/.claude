#!/usr/bin/env bats
# CI bridge for hooks/tests/test-quality-gate-freshness.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-quality-gate-freshness harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-quality-gate-freshness.sh"; [ "$status" -eq 0 ]; }
@test "test-quality-gate-freshness reports 28 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-quality-gate-freshness.sh"; echo "$output" | grep -q "28 passed, 0 failed"; }

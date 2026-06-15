#!/usr/bin/env bats
# CI bridge for hooks/tests/test-cost-feed-router-signals.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-cost-feed-router-signals harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-cost-feed-router-signals.sh"; [ "$status" -eq 0 ]; }
@test "test-cost-feed-router-signals reports 10/10 passed" { run bash "$REPO_ROOT/hooks/tests/test-cost-feed-router-signals.sh"; echo "$output" | grep -q "10/10 passed"; }

#!/usr/bin/env bats
# CI bridge for hooks/tests/test-eval-model-effectiveness.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-eval-model-effectiveness harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-eval-model-effectiveness.sh"; [ "$status" -eq 0 ]; }
@test "test-eval-model-effectiveness reports 17 passed, 0 failed" { run bash "$REPO_ROOT/hooks/tests/test-eval-model-effectiveness.sh"; echo "$output" | grep -q "17 passed, 0 failed"; }

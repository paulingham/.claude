#!/usr/bin/env bats
# CI bridge for hooks/tests/test-eval-capture-hook.sh — runs the external harness so CI gates on it.
setup() { REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"; }
@test "test-eval-capture-hook harness exits 0" { run bash "$REPO_ROOT/hooks/tests/test-eval-capture-hook.sh"; [ "$status" -eq 0 ]; }
@test "test-eval-capture-hook reports fail=0" { run bash "$REPO_ROOT/hooks/tests/test-eval-capture-hook.sh"; echo "$output" | grep -q "fail=0"; }

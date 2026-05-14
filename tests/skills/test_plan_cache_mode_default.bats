#!/usr/bin/env bats
# Slice B — AC B6: CLAUDE_PLAN_CACHE_MODE resolver default.
# Plan: § slice-b. Hard-default `off` ships in Slice B (LOW-eng-3
# partial-merge safety); Slice F flips default to `shadow`.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/plan-cache-lookup.sh"
}

@test "B6 unset CLAUDE_PLAN_CACHE_MODE resolves to off in Slice B" {
  unset CLAUDE_PLAN_CACHE_MODE
  # shellcheck source=/dev/null
  source "$LIB"
  run _plan_cache_mode
  [ "$status" -eq 0 ]
  [ "$output" = "off" ]
}

@test "B6b explicit shadow mode is honoured" {
  export CLAUDE_PLAN_CACHE_MODE=shadow
  # shellcheck source=/dev/null
  source "$LIB"
  run _plan_cache_mode
  [ "$status" -eq 0 ]
  [ "$output" = "shadow" ]
}

@test "B6c invalid mode value falls back to off" {
  export CLAUDE_PLAN_CACHE_MODE=garbage
  # shellcheck source=/dev/null
  source "$LIB"
  run _plan_cache_mode
  [ "$status" -eq 0 ]
  [ "$output" = "off" ]
}

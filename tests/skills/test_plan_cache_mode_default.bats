#!/usr/bin/env bats
# Slice B/F — CLAUDE_PLAN_CACHE_MODE resolver.
# Plan: § slice-b (hard-default `off` for partial-merge safety) → § slice-f
# (default flipped to `shadow`). The unset-default assertion lives in
# tests/skills/test_plan_cache_mode.bats § F1 (authoritative). This file keeps
# the explicit-value branches as ratchet-coverage.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/plan-cache-lookup.sh"
}

@test "B6 unset CLAUDE_PLAN_CACHE_MODE resolves to shadow after Slice F flip" {
  unset CLAUDE_PLAN_CACHE_MODE
  # shellcheck source=/dev/null
  source "$LIB"
  run _plan_cache_mode
  [ "$status" -eq 0 ]
  [ "$output" = "shadow" ]
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

#!/usr/bin/env bats
# Unit tests for hooks/_lib/check-bypass-gate.sh
# AC1: file exists and defines check_bypass_gate with no side effects.
# AC3: correct return codes for all bypass-gate inputs.
# AC2 (slice-b): no surviving inline CLAUDE_DISABLE_* bypass checks in hooks.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HELPER="$REPO_ROOT/hooks/_lib/check-bypass-gate.sh"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  # Ensure no bypass vars leak from caller environment.
  unset BYPASS_TEST_VAR ANOTHER_TEST_VAR
}

teardown() {
  unset BYPASS_TEST_VAR ANOTHER_TEST_VAR
}

# ---------------------------------------------------------------------------
# AC1 + AC3: helper contract
# ---------------------------------------------------------------------------

@test "AC1 sourcing check-bypass-gate.sh defines check_bypass_gate function" {
  # File must exist and source cleanly.
  [ -f "$HELPER" ]
  # shellcheck source=/dev/null
  source "$HELPER"
  declare -f check_bypass_gate >/dev/null
}

@test "AC1 sourcing produces no stdout" {
  output=$(source "$HELPER" 2>/dev/null)
  [ -z "$output" ]
}

@test "AC1 sourcing produces no stderr" {
  errs=$(source "$HELPER" 2>&1 >/dev/null)
  [ -z "$errs" ]
}

@test "AC1 sourcing creates no stray files" {
  TMP_CHECK="$(mktemp -d)"
  (cd "$TMP_CHECK" && source "$REPO_ROOT/hooks/_lib/check-bypass-gate.sh")
  count=$(find "$TMP_CHECK" -mindepth 1 | wc -l | tr -d ' ')
  rm -rf "$TMP_CHECK"
  [ "$count" -eq 0 ]
}

@test "AC3 VAR unset -> returns 1 (no bypass)" {
  source "$HELPER"
  unset BYPASS_TEST_VAR
  ! check_bypass_gate "BYPASS_TEST_VAR"
}

@test "AC3 VAR=1 -> returns 0 (bypass)" {
  source "$HELPER"
  BYPASS_TEST_VAR=1
  check_bypass_gate "BYPASS_TEST_VAR"
}

@test "AC3 VAR=0 -> returns 1 (no bypass)" {
  source "$HELPER"
  BYPASS_TEST_VAR=0
  ! check_bypass_gate "BYPASS_TEST_VAR"
}

@test "AC3 VAR=true -> returns 1 (exact == 1 semantics)" {
  source "$HELPER"
  BYPASS_TEST_VAR=true
  ! check_bypass_gate "BYPASS_TEST_VAR"
}

@test "AC3 VAR=yes -> returns 1 (exact == 1 semantics)" {
  source "$HELPER"
  BYPASS_TEST_VAR=yes
  ! check_bypass_gate "BYPASS_TEST_VAR"
}

@test "AC3 VAR=empty-string -> returns 1 (exact == 1 semantics)" {
  source "$HELPER"
  BYPASS_TEST_VAR=""
  ! check_bypass_gate "BYPASS_TEST_VAR"
}

# AC3/4b: Class-1b equivalence — original used ${VAR:-} (empty fallback).
# check_bypass_gate uses ${!1:-0}; with VAR unset, both yield non-"1" -> rc1.
@test "AC4b Class-1b empty-fallback equivalence: unset VAR -> returns 1 (identical to original empty-!='1' outcome)" {
  source "$HELPER"
  unset BYPASS_TEST_VAR
  # Simulate the Class-1b shape: unset var, empty default, != "1" -> no bypass.
  ! check_bypass_gate "BYPASS_TEST_VAR"
}

# ---------------------------------------------------------------------------
# AC2 (slice-b): no surviving inline bypass in hooks/ (excluding _lib/ and tests/).
# This test will be RED until all Class-1/1b/2 sites are migrated in slice-b.
# Run from REPO_ROOT. Must return ZERO matches.
# ---------------------------------------------------------------------------

@test "AC2 no surviving inline CLAUDE_DISABLE_* bypass checks in hooks/ (excluding _lib/ and tests/)" {
  # This grep matches only the inline [[ "${CLAUDE_DISABLE_X:-..}" == "1" ]] shape.
  # It does NOT match:
  #   - help-text/comment mentions (no [[ ]] structure)
  #   - the helper's own ${!1:-0} implementation (different — excluded by path)
  #   - Python-delegated sites (no bash [[ ]])
  result=$(grep -rEn '\[\[[[:space:]]*"\$\{CLAUDE_DISABLE_[A-Z_]+:-[^}]*\}"[[:space:]]*==[[:space:]]*"1"[[:space:]]*\]\]' \
    "$REPO_ROOT/hooks" --include='*.sh' \
    | grep -v 'hooks/_lib/' | grep -v 'hooks/tests/' | grep -v 'check-bypass-gate.sh' \
    || true)
  [ -z "$result" ]
}

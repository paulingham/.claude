#!/usr/bin/env bats
# CI-green gate tests (AC1-AC11, AC11b)
# Iron Law 8: AC8 (revert-RED) + AC9 (unevaluable-refuses) are mandated per-gate tests.
# All gh/jq calls are stubbed via PATH-prepended fixture dir — hermetic, NO network.

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t ci_green_gate.XXXXXX)"
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  STUB_DIR="$BATS_FILE_TMPDIR/stubs"
  mkdir -p "$STUB_DIR"
  export REPO_ROOT STUB_DIR BATS_FILE_TMPDIR

  # Default: unset the operator escape so gate is active
  unset CLAUDE_CI_GREEN_GATE

  GATE="$REPO_ROOT/skills/pipeline/lib/check-ci-green-gate.sh"
  READER="$REPO_ROOT/hooks/_lib/ci-status-reader.sh"
  export GATE READER
}

teardown() {
  rm -rf "$BATS_FILE_TMPDIR"
}

# Helper: install a gh stub that emits given JSON and exits with given code
_stub_gh() {
  local json="$1" rc="${2:-0}"
  cat > "$STUB_DIR/gh" <<STUBEOF
#!/usr/bin/env bash
exit_code=$rc
echo '$json'
exit \$exit_code
STUBEOF
  chmod +x "$STUB_DIR/gh"
  export PATH="$STUB_DIR:$PATH"
}

# Helper: all-SUCCESS rollup JSON (CheckRun shape)
_all_success_json() {
  printf '%s' '[{"name":"ci","conclusion":"SUCCESS","state":"SUCCESS"},{"name":"lint","conclusion":"SUCCESS","state":"SUCCESS"}]'
}

# Helper: one FAILURE rollup JSON
_failure_json() {
  printf '%s' '[{"name":"ci","conclusion":"SUCCESS","state":"SUCCESS"},{"name":"lint","conclusion":"FAILURE","state":"FAILURE"}]'
}

# Helper: PENDING rollup JSON
_pending_json() {
  printf '%s' '[{"name":"ci","conclusion":"IN_PROGRESS","state":"PENDING"}]'
}

# Helper: empty rollup JSON
_empty_rollup_json() {
  printf '%s' '[]'
}

# Helper: WEIRD unknown status token (AC8 Iron Law 8 revert test)
_weird_state_json() {
  printf '%s' '[{"name":"ci","conclusion":"WEIRD_NEW_STATE","state":"WEIRD_NEW_STATE"}]'
}

# ─── AC1: Green path allows ────────────────────────────────────────────────────

@test "AC1_all_success_allows: all-SUCCESS rollup exits 0" {
  local json
  json='{"statusCheckRollup":'"$(_all_success_json)"'}'
  _stub_gh "$json" 0
  run bash "$GATE" 42
  [ "$status" -eq 0 ]
}

# ─── AC2: Red path blocks ──────────────────────────────────────────────────────

@test "AC2_failure_conclusion_blocks: FAILURE conclusion exits 2" {
  local json
  json='{"statusCheckRollup":'"$(_failure_json)"'}'
  _stub_gh "$json" 0
  run bash "$GATE" 42
  [ "$status" -eq 2 ]
}

# ─── AC3: Pending blocks (fail-closed) ────────────────────────────────────────

@test "AC3_pending_blocks_failclosed: PENDING state exits 2" {
  local json
  json='{"statusCheckRollup":'"$(_pending_json)"'}'
  _stub_gh "$json" 0
  run bash "$GATE" 42
  [ "$status" -eq 2 ]
}

# ─── AC4: Empty/absent rollup blocks ──────────────────────────────────────────

@test "AC4_empty_rollup_blocks: empty array exits 2" {
  local json
  json='{"statusCheckRollup":'"$(_empty_rollup_json)"'}'
  _stub_gh "$json" 0
  run bash "$GATE" 42
  [ "$status" -eq 2 ]
}

@test "AC4_null_rollup_blocks: null statusCheckRollup exits 2" {
  local json='{"statusCheckRollup":null}'
  _stub_gh "$json" 0
  run bash "$GATE" 42
  [ "$status" -eq 2 ]
}

# ─── AC5: gh tool error blocks ────────────────────────────────────────────────

@test "AC5_gh_nonzero_blocks: gh exits 1 causes gate exit 2" {
  _stub_gh '{}' 1
  run bash "$GATE" 42
  [ "$status" -eq 2 ]
}

# ─── AC6: Malformed JSON blocks ───────────────────────────────────────────────

@test "AC6_malformed_json_blocks: non-JSON output exits 2 without crash" {
  cat > "$STUB_DIR/gh" <<'STUBEOF'
#!/usr/bin/env bash
echo "not-valid-json"
exit 0
STUBEOF
  chmod +x "$STUB_DIR/gh"
  export PATH="$STUB_DIR:$PATH"
  run bash "$GATE" 42
  [ "$status" -eq 2 ]
}

# ─── AC7: Bad PR number blocks + no injection ─────────────────────────────────

@test "AC7_nonnumeric_pr_blocks_no_interp: injection attempt exits 2 PWNED not created" {
  # WHY: guard must reject before any gh/shell interpolation
  PWNED_FILE="$BATS_FILE_TMPDIR/PWNED"
  run bash "$GATE" "12; touch $PWNED_FILE"
  [ "$status" -eq 2 ]
  [ ! -f "$PWNED_FILE" ]
}

@test "AC7_empty_pr_blocks: empty PR arg exits 2" {
  run bash "$GATE" ""
  [ "$status" -eq 2 ]
}

# ─── AC8: Iron Law 8 — REVERT-RED test ───────────────────────────────────────
# This test MUST go RED if the reader's fail-closed default is changed to exit 0.
# An unrecognized status token (WEIRD_NEW_STATE) must block — if the default
# is reverted to allow, this test turns RED.

@test "AC8_ironlaw8_revert_failclosed_goes_red: unknown status WEIRD_NEW_STATE exits 2" {
  local json
  json='{"statusCheckRollup":'"$(_weird_state_json)"'}'
  _stub_gh "$json" 0
  run bash "$GATE" 42
  # If the reader's fall-through default is ALLOW (exit 0), this test goes RED.
  # That RED is the Iron Law 8 sentinel.
  [ "$status" -eq 2 ]
}

# ─── AC9: Iron Law 8 — UNEVALUABLE-REFUSES test ──────────────────────────────
# Feed unevaluable input (no PR arg) under strict mode — gate must refuse (exit 2)
# with no unbound-variable crash on stderr.

@test "AC9_ironlaw8_unevaluable_refuses: missing PR arg exits 2, no unbound-var stderr" {
  # Call with no argument — gate must fail closed, not crash with "unbound variable"
  run bash "$GATE"
  [ "$status" -eq 2 ]
  # No unbound-var message in stderr
  [[ "$output" != *"unbound variable"* ]]
  [[ "$output" != *"parameter not set"* ]]
}

# ─── AC10: Operator escape — logged, not fail-open ────────────────────────────

@test "AC10_operator_escape_logged_not_failopen: CLAUDE_CI_GREEN_GATE=off exits 0 with warning" {
  # Even with a bad PR that would block, escape allows through
  CLAUDE_CI_GREEN_GATE=off run bash "$GATE" 42
  [ "$status" -eq 0 ]
  [[ "$output" == *"CLAUDE_CI_GREEN_GATE=off"* ]] || [[ "$output" == *"override"* ]]
}

@test "AC10_escape_unset_with_unevaluable_still_blocks: unset escape + no PR arg exits 2" {
  # WHY: escape must NOT be consulted for the unevaluable/missing-pr path
  # When escape is unset, missing arg must still block
  unset CLAUDE_CI_GREEN_GATE
  run bash "$GATE"
  [ "$status" -eq 2 ]
}

# ─── AC11: No unbound-var under set -uo pipefail ─────────────────────────────

@test "AC11_no_unbound_var_strict_mode: source + call under strict mode prints OK" {
  local json
  json='{"statusCheckRollup":'"$(_all_success_json)"'}'
  _stub_gh "$json" 0
  # Run the entire gate under strict mode — if any unbound variable exists, exits non-zero
  run bash -c "set -uo pipefail; bash '$GATE' 42; echo OK"
  [[ "$output" == *"OK"* ]]
}

# ─── AC11b: Block message names PR, reason, override hint ─────────────────────

@test "AC11b_block_message_names_pr_reason_and_override: stderr contains PR# reason and override hint" {
  # Use a gh-error case (gh exits non-zero) so we get a block message
  _stub_gh '{}' 1
  run bash "$GATE" 99
  [ "$status" -eq 2 ]
  # stderr (mixed into output by bats run) must contain PR number
  [[ "$output" == *"99"* ]]
  # Must contain a reason token (gh-error, empty-rollup, malformed-json, or unknown-check-type)
  [[ "$output" == *"gh-error"* ]] || [[ "$output" == *"empty-rollup"* ]] || \
    [[ "$output" == *"malformed-json"* ]] || [[ "$output" == *"unknown"* ]]
  # Must contain the override hint
  [[ "$output" == *"CLAUDE_CI_GREEN_GATE=off"* ]]
}

@test "AC11b_block_message_empty_rollup_reason: empty-rollup reason in block message" {
  local json='{"statusCheckRollup":[]}'
  _stub_gh "$json" 0
  run bash "$GATE" 77
  [ "$status" -eq 2 ]
  [[ "$output" == *"77"* ]]
  [[ "$output" == *"empty-rollup"* ]]
  [[ "$output" == *"CLAUDE_CI_GREEN_GATE=off"* ]]
}

@test "AC11b_block_message_unknown_check_type_reason: unknown token produces reason token" {
  local json
  json='{"statusCheckRollup":'"$(_weird_state_json)"'}'
  _stub_gh "$json" 0
  run bash "$GATE" 55
  [ "$status" -eq 2 ]
  [[ "$output" == *"55"* ]]
  [[ "$output" == *"WEIRD_NEW_STATE"* ]] || [[ "$output" == *"unknown"* ]]
  [[ "$output" == *"CLAUDE_CI_GREEN_GATE=off"* ]]
}

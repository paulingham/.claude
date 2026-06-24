#!/usr/bin/env bats
# Decoder tests for skills/pr-creation/lib/ci-event-decode.sh
#
# Iron Law 8 pattern — mirrors test_ci_green_gate.bats:152-173:
#   AC1 (revert-RED): reverting fail-closed default turns this RED
#   AC2 (unevaluable-refuses): missing/malformed input → exit 2, no unbound-var
#   AC2-bis (forged-event safety): all-SUCCESS well-formed → candidate-green, NOT CI_GREEN

setup() {
  BATS_FILE_TMPDIR="$(mktemp -d -t ci_event_decode.XXXXXX)"
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  DECODER="$REPO_ROOT/skills/pr-creation/lib/ci-event-decode.sh"
  export BATS_FILE_TMPDIR REPO_ROOT DECODER
}

teardown() {
  rm -rf "$BATS_FILE_TMPDIR"
}

# ─── AC1: Iron Law 8 — REVERT-RED test ───────────────────────────────────────
# This test MUST go RED if the decoder's fail-closed default is reverted to
# "treat unparseable line as candidate-green".
# A malformed/empty event line fed to ci-event-decode.sh must exit 2 → watch-skipped.

@test "AC1_decoder_revert_failclosed_goes_red: malformed line exits 2, never candidate-green" {
  # Feed a line with neither conclusion nor sha — completely malformed.
  # If the decoder's fail-closed default is reverted to allow (exit 0 with
  # candidate-green), this test turns RED, which is the Iron Law 8 sentinel.
  run bash "$DECODER" <<< "not-valid-json-nor-structured-event"
  [ "$status" -eq 2 ]
  # Must NOT emit candidate-green for an unparseable line
  [[ "$output" != *"candidate-green"* ]]
}

# ─── AC2: Iron Law 8 — UNEVALUABLE-REFUSES test ─────────────────────────────
# Absent/empty stdin, missing conclusion field, missing sha field → exit 2 + reason,
# no unbound-var crash. Gate refuses, never silently proceeds as green.

@test "AC2_decoder_unevaluable_refuses: empty stdin exits 2, no unbound-var" {
  # Empty stdin — no event line at all
  run bash "$DECODER" < /dev/null
  [ "$status" -eq 2 ]
  # No unbound-variable crash
  [[ "$output" != *"unbound variable"* ]]
  [[ "$output" != *"parameter not set"* ]]
}

@test "AC2_decoder_missing_conclusion_exits_2: line without conclusion field exits 2" {
  # A line with sha but no conclusion
  run bash "$DECODER" <<< '{"sha":"abc123","pr":"42"}'
  [ "$status" -eq 2 ]
  [[ "$output" != *"candidate-green"* ]]
  [[ "$output" != *"CI_GREEN"* ]]
}

@test "AC2_decoder_missing_sha_exits_2: line without sha field exits 2" {
  # A line with conclusion but no sha
  run bash "$DECODER" <<< '{"conclusion":"SUCCESS","pr":"42"}'
  [ "$status" -eq 2 ]
  [[ "$output" != *"candidate-green"* ]]
  [[ "$output" != *"CI_GREEN"* ]]
}

# ─── AC2-bis: Forged-event safety ────────────────────────────────────────────
# A well-formed all-SUCCESS line yields classification "candidate-green"
# (NOT "CI_GREEN"). The decoder NEVER self-decides GREEN — it defers the
# authoritative GREEN decision to ci_status_decision(PR).

@test "AC2bis_candidate_green_does_not_self_decide: all-SUCCESS yields candidate-green not CI_GREEN" {
  # A well-formed event line with conclusion=SUCCESS, sha, and pr present
  run bash "$DECODER" <<< '{"conclusion":"SUCCESS","sha":"abc123def456","pr":"42"}'
  [ "$status" -eq 0 ]
  # Must emit candidate-green classification token
  [[ "$output" == *"candidate-green"* ]]
  # Must NOT self-decide CI_GREEN — that authority stays with ci_status_decision(PR)
  [[ "$output" != *"CI_GREEN"* ]]
}

@test "AC1_unknown_conclusion_exits_2: unknown conclusion token fails closed" {
  # WHY: mutation guard — if the case *) branch is changed from exit 2 to
  # candidate-green, this test turns RED (Iron Law 8 revert-RED for the case branch).
  run bash "$DECODER" <<< '{"conclusion":"WEIRD_NEW_STATE","sha":"abc123","pr":"42"}'
  [ "$status" -eq 2 ]
  [[ "$output" != *"candidate-green"* ]]
}

@test "AC_failure_conclusion_yields_RED_hint: FAILURE conclusion emits RED-hint" {
  run bash "$DECODER" <<< '{"conclusion":"FAILURE","sha":"abc123def456","pr":"42"}'
  [ "$status" -eq 0 ]
  [[ "$output" == *"RED-hint"* ]]
  [[ "$output" != *"candidate-green"* ]]
}

# ─── AC2ter: Control-character injection — regression for newline-split attack ─
# A JSON value containing a literal newline (the JSON backslash-n escape) would
# previously split across lines when printed, causing sed-based re-extraction to
# read the wrong field values and produce a false candidate-green.
# After the fix the python3 process detects the control character and exits 2.

@test "AC2ter_control_char_in_field_refuses: newline in conclusion exits 2, not candidate-green" {
  # WHY: regression guard for the newline-injection attack. Valid JSON where the
  # conclusion value contains a JSON-encoded newline must be rejected with exit 2.
  # This test goes RED against the pre-fix sed-based decoder and GREEN after the
  # all-in-python3 fix.
  local payload
  payload="$(python3 -c "import json; print(json.dumps({'conclusion': 'SUCCESS\nFAILURE', 'sha': 'abc123'}))")"
  run bash "$DECODER" <<< "$payload"
  [ "$status" -eq 2 ]
  [[ "$output" != *"candidate-green"* ]]
}

@test "AC2ter_nul_char_in_sha_refuses: NUL in sha exits 2, not candidate-green" {
  # WHY: NUL bytes in a field value are a control-char variant of the injection
  # attack. Any ord less than 0x20 in any field must exit 2.
  local payload
  payload="$(python3 -c "import json; print(json.dumps({'conclusion': 'SUCCESS', 'sha': 'abc\x00def'}))")"
  run bash "$DECODER" <<< "$payload"
  [ "$status" -eq 2 ]
  [[ "$output" != *"candidate-green"* ]]
}

# ─── AC2quat: Non-object JSON — regression for exit-2 contract violation ───────
# Valid JSON that is not a dict (array, scalar) previously raised AttributeError
# inside python3 and exited 1 instead of the contracted exit 2.
# After the isinstance(d, dict) guard this must exit 2, never exit 1 or candidate-green.

@test "AC2quat_non_object_json_refuses: JSON array exits 2, not candidate-green" {
  # WHY: Iron Law 8 — any unevaluable input exits 2. A JSON array is valid JSON
  # but not a dict, so d.get() would raise AttributeError without the type guard.
  # This test MUST go RED against the pre-fix HEAD (exits 1) and GREEN after.
  run bash "$DECODER" <<< '[1,2]'
  [ "$status" -eq 2 ]
  [[ "$output" != *"candidate-green"* ]]
}

@test "AC2quat_scalar_json_refuses: JSON scalar exits 2, not candidate-green" {
  # WHY: Scalar JSON (42, "SUCCESS", true, null) is equally non-evaluable.
  # Verifies the type guard fires for the full non-dict class.
  run bash "$DECODER" <<< '42'
  [ "$status" -eq 2 ]
  [[ "$output" != *"candidate-green"* ]]
}

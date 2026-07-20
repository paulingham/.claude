#!/usr/bin/env bats
# Behavioral tests for hooks/_lib/build_result_reader.py (stall-fix completion signal).
# Fail-closed contract (Iron Law 8): absent/corrupt file must NEVER read as COMPLETE.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  READER="$REPO_ROOT/hooks/_lib/build_result_reader.py"
  TMP="$(mktemp -d -t build_result.XXXXXX)"
  TASK_ID="demo-task"
  mkdir -p "$TMP/$TASK_ID"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

write_result() {
  printf '%s' "$1" > "$TMP/$TASK_ID/build-result.json"
}

read_status() {
  python3 "$READER" "$TMP" "$TASK_ID"
}

@test "AC1 valid BUILD_COMPLETE reads COMPLETE with branch and head_sha" {
  write_result '{"schema_version":1,"agent_role":"software-engineer","verdict":"BUILD_COMPLETE","branch":"feat/x","head_sha":"abc123","base_sha":"main","green":true,"unresolved":[],"generated_at":"2026-07-20T00:00:00Z"}'
  run read_status
  [ "$status" -eq 0 ]
  [[ "$output" == *'"status": "COMPLETE"'* ]]
  [[ "$output" == *'"branch": "feat/x"'* ]]
  [[ "$output" == *'"head_sha": "abc123"'* ]]
}

@test "AC2 missing file reads MISSING and never COMPLETE" {
  run read_status
  [ "$status" -eq 0 ]
  [[ "$output" == *'"status": "MISSING"'* ]]
  [[ "$output" != *'"status": "COMPLETE"'* ]]
}

@test "AC3a corrupt unparseable JSON reads CORRUPT and never COMPLETE" {
  write_result '{'
  run read_status
  [ "$status" -eq 0 ]
  [[ "$output" == *'"status": "CORRUPT"'* ]]
  [[ "$output" != *'"status": "COMPLETE"'* ]]
}

@test "AC3b corrupt empty file reads CORRUPT and never COMPLETE" {
  write_result ''
  run read_status
  [ "$status" -eq 0 ]
  [[ "$output" == *'"status": "CORRUPT"'* ]]
  [[ "$output" != *'"status": "COMPLETE"'* ]]
}

@test "AC3c corrupt unknown verdict reads CORRUPT and never COMPLETE" {
  write_result '{"verdict":"WAT","branch":"b","head_sha":"h"}'
  run read_status
  [ "$status" -eq 0 ]
  [[ "$output" == *'"status": "CORRUPT"'* ]]
  [[ "$output" != *'"status": "COMPLETE"'* ]]
}

@test "AC3d corrupt missing required field reads CORRUPT and never COMPLETE" {
  write_result '{"verdict":"BUILD_COMPLETE","branch":"b"}'
  run read_status
  [ "$status" -eq 0 ]
  [[ "$output" == *'"status": "CORRUPT"'* ]]
  [[ "$output" != *'"status": "COMPLETE"'* ]]
}

@test "AC4 BUILD_FAILED verdict reads FAILED and surfaces unresolved" {
  write_result '{"verdict":"BUILD_FAILED","branch":"feat/x","head_sha":"abc123","unresolved":["AC2 test still red"]}'
  run read_status
  [ "$status" -eq 0 ]
  [[ "$output" == *'"status": "FAILED"'* ]]
  [[ "$output" == *"AC2 test still red"* ]]
}

# RED-on-revert canary: if the fail-closed guard in _load/_classify is
# reverted to a fall-through (e.g. returning the raw parsed dict without
# classification on error), a missing or corrupt file could start reading
# as COMPLETE. This test asserts the never-COMPLETE invariant directly
# across both unevaluable-input classes in one assertion pass, so a revert
# that reintroduces a fall-through path goes RED here even if AC2/AC3 above
# are individually weakened.
@test "CANARY fail-closed guard: neither missing nor corrupt input ever yields COMPLETE" {
  run read_status
  [[ "$output" != *'"status": "COMPLETE"'* ]]

  write_result '{not json'
  run read_status
  [[ "$output" != *'"status": "COMPLETE"'* ]]
}

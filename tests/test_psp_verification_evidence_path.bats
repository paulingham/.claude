#!/usr/bin/env bats
# Slice 2: _psp_verification_evidence_path helper in pipeline-state-paths.sh.
# AC2.1: helper returns the per-task verification-evidence.json path.
#        Workstream variant supported. Follows the _psp_ prefix convention.

setup() {
  HELPERS="${BATS_TEST_DIRNAME}/../hooks/_lib/pipeline-state-paths.sh"
  # shellcheck source=/dev/null
  source "$HELPERS"
}

@test "helper_returns_root_path_when_no_workstream" {
  run _psp_verification_evidence_path "my-task" ""
  [ "$status" -eq 0 ]
  [ "$output" = "pipeline-state/my-task/verification-evidence.json" ]
}

@test "helper_returns_workstream_path_when_ws_set" {
  run _psp_verification_evidence_path "my-task" "my-ws"
  [ "$status" -eq 0 ]
  [ "$output" = "pipeline-state/workstreams/my-ws/my-task/verification-evidence.json" ]
}

@test "helper_uses_psp_prefix_per_convention" {
  # The helper must be named with the _psp_ prefix to match sibling helpers
  # (_psp_task_state_path, _psp_legacy_state_path, etc.).
  run grep -E '^_psp_verification_evidence_path\(\)' "$HELPERS"
  [ "$status" -eq 0 ]
}

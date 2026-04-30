#!/usr/bin/env bats
# Slice A — bash helper contract for new-layout pipeline-state paths.
# Locks the relative-path convention `_psp_task_state_path TASK PHASE`
# echoes, which Slice B/C consumers (skills + hooks) rely on.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/pipeline-state-paths.sh"
}

@test "_psp_task_state_path emits new-layout path" {
  run bash -c "source '$LIB'; _psp_task_state_path tk-1 build"
  [ "$status" -eq 0 ]
  [ "$output" = "pipeline-state/tk-1/build.md" ]
}

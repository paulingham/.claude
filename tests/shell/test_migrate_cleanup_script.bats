#!/usr/bin/env bats
# Slice F (AC #7) — migration script cleanup tests.
# Verifies scripts/migrate-pipeline-state.sh removes terminal pre-existing
# pipelines, refuses non-terminal or partial-cleanup state, preserves audit
# references, and is idempotent. All tests run against a fixture
# pipeline-state directory created in BATS_FILE_TMPDIR — never against the
# real ~/.claude/pipeline-state.

setup_file() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  export REPO_ROOT
  SCRIPT="$REPO_ROOT/scripts/migrate-pipeline-state.sh"
  export SCRIPT
}

setup() {
  source "$REPO_ROOT/tests/_fixtures/pipeline_state.sh"
  BATS_FILE_TMPDIR="$(mktemp -d -t slicef.XXXXXX)"
  export PIPELINE_DIR="$BATS_FILE_TMPDIR"
  [ -x "$SCRIPT" ]
}

teardown() { rm -rf "$BATS_FILE_TMPDIR"; }

_seed_terminal_pipeline() {
  local prefix="$1" verdict="$2"
  _psf_make_fixture --task-id="$prefix" --layout=legacy --verdict="$verdict" \
    --phases='pipeline build' "$PIPELINE_DIR" >/dev/null
  mkdir -p "$PIPELINE_DIR/${prefix}-scratchpad"
  printf 'note\n' > "$PIPELINE_DIR/${prefix}-scratchpad/build-build.md"
  printf 'APPROVED\n' > "$PIPELINE_DIR/${prefix}-approval.token"
}

@test "cleanup_removes_thinking_defaults_xhigh_files" {
  _seed_terminal_pipeline thinking-defaults-xhigh PR_CREATED
  PIPELINE_STATE_DIR="$PIPELINE_DIR" run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ ! -e "$PIPELINE_DIR/thinking-defaults-xhigh-pipeline.md" ]
  [ ! -e "$PIPELINE_DIR/thinking-defaults-xhigh-build.md" ]
  [ ! -e "$PIPELINE_DIR/thinking-defaults-xhigh-approval.token" ]
  [ ! -d "$PIPELINE_DIR/thinking-defaults-xhigh-scratchpad" ]
}

@test "cleanup_removes_wave4_S_files" {
  _seed_terminal_pipeline wave4-S completed
  PIPELINE_STATE_DIR="$PIPELINE_DIR" run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ ! -e "$PIPELINE_DIR/wave4-S-pipeline.md" ]
  [ ! -e "$PIPELINE_DIR/wave4-S-build.md" ]
  [ ! -d "$PIPELINE_DIR/wave4-S-scratchpad" ]
}

@test "cleanup_refuses_to_delete_in_progress_pipeline" {
  _seed_terminal_pipeline wave4-S in_progress
  PIPELINE_STATE_DIR="$PIPELINE_DIR" run "$SCRIPT"
  [ "$status" -ne 0 ]
  [ -f "$PIPELINE_DIR/wave4-S-pipeline.md" ]
  [ -f "$PIPELINE_DIR/wave4-S-build.md" ]
}

@test "cleanup_refuses_when_phase_files_present_without_pipeline_md" {
  printf 'green\n' > "$PIPELINE_DIR/wave4-S-build.md"
  mkdir -p "$PIPELINE_DIR/wave4-S-scratchpad"
  PIPELINE_STATE_DIR="$PIPELINE_DIR" run "$SCRIPT"
  [ "$status" -ne 0 ]
  [ -f "$PIPELINE_DIR/wave4-S-build.md" ]
  [ -d "$PIPELINE_DIR/wave4-S-scratchpad" ]
}

@test "cleanup_accepts_terminal_verdict_allowlist" {
  for verdict in completed PR_CREATED MERGED FAILED REJECTED; do
    rm -rf "$PIPELINE_DIR"; mkdir -p "$PIPELINE_DIR"
    _seed_terminal_pipeline wave4-S "$verdict"
    PIPELINE_STATE_DIR="$PIPELINE_DIR" run "$SCRIPT"
    [ "$status" -eq 0 ] || { echo "verdict=$verdict refused"; return 1; }
    [ ! -e "$PIPELINE_DIR/wave4-S-pipeline.md" ]
  done
}

@test "cleanup_does_not_touch_audit_sonnet_context_200k" {
  printf 'plan\n' > "$PIPELINE_DIR/audit-sonnet-context-200k-plan.md"
  mkdir -p "$PIPELINE_DIR/audit-sonnet-context-200k-scratchpad"
  printf 'note\n' > "$PIPELINE_DIR/audit-sonnet-context-200k-scratchpad/architect-plan.md"
  _seed_terminal_pipeline wave4-S completed
  PIPELINE_STATE_DIR="$PIPELINE_DIR" run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ -f "$PIPELINE_DIR/audit-sonnet-context-200k-plan.md" ]
  [ -d "$PIPELINE_DIR/audit-sonnet-context-200k-scratchpad" ]
  [ -f "$PIPELINE_DIR/audit-sonnet-context-200k-scratchpad/architect-plan.md" ]
}

@test "cleanup_is_idempotent" {
  _seed_terminal_pipeline wave4-S completed
  PIPELINE_STATE_DIR="$PIPELINE_DIR" run "$SCRIPT"
  [ "$status" -eq 0 ]
  PIPELINE_STATE_DIR="$PIPELINE_DIR" run "$SCRIPT"
  [ "$status" -eq 0 ]
  [ ! -e "$PIPELINE_DIR/wave4-S-pipeline.md" ]
}

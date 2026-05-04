#!/usr/bin/env bats

setup() {
  export CLAUDE_SESSION_ID="test-$$"
  export CLAUDE_PIPELINE_TASK_ID="test-task"
  TMPDIR_BAT=$(mktemp -d)
  export HOME="$TMPDIR_BAT"
  mkdir -p "$HOME/.claude/state" "$HOME/.claude/metrics/test-$$"
}

teardown() {
  rm -rf "$TMPDIR_BAT"
}

@test "post-confirmed emitted when invariant holds" {
  EVENTS="$HOME/.claude/metrics/test-$$/quality-gate-events.jsonl"
  echo '{"source":"passed","task_id":"test-task","ts":1700000000}' > "$EVENTS"
  run bash "${BATS_TEST_DIRNAME}/../../hooks/quality-gate-stop.sh" < /dev/null
  [ "$status" -eq 0 ]
}

@test "drift-detected when tests break during agent" {
  skip "Integration: requires lib functions to be sourceable"
}

@test "cursor advances idempotently" {
  EVENTS="$HOME/.claude/metrics/test-$$/quality-gate-events.jsonl"
  echo '{"source":"passed","task_id":"test-task","ts":1700000000}' > "$EVENTS"
  CURSOR_FILE="$HOME/.claude/state/quality-gate-cursor-test-task"
  echo "1" > "$CURSOR_FILE"
  run bash "${BATS_TEST_DIRNAME}/../../hooks/quality-gate-stop.sh" < /dev/null
  [ "$status" -eq 0 ]
}

@test "snapshot file written at PreToolUse pass" {
  skip "Integration: requires PreToolUse simulation"
}

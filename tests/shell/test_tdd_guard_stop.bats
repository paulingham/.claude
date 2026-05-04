#!/usr/bin/env bats

setup() {
  export CLAUDE_SESSION_ID="test-$$"
  export CLAUDE_PIPELINE_TASK_ID="test-task"
  TMPDIR_BAT=$(mktemp -d)
  export HOME="$TMPDIR_BAT"
  mkdir -p "$HOME/.claude/state" "$HOME/.claude/metrics/test-$$"
}

teardown() { rm -rf "$TMPDIR_BAT"; }

@test "tdd post-confirmed when diff still balanced" {
  EVENTS="$HOME/.claude/metrics/test-$$/tdd-guard-events.jsonl"
  echo '{"source":"passed","task_id":"test-task","ts":1700000000}' > "$EVENTS"
  echo '{"diff_files":3}' > "$HOME/.claude/state/tdd-guard-diff-snapshot-test-task.json"
  run bash "${BATS_TEST_DIRNAME}/../../hooks/tdd-guard-stop.sh" < /dev/null
  [ "$status" -eq 0 ]
}

@test "tdd drift-detected when tests removed post pass" {
  skip "Integration: requires git state setup"
}

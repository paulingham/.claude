#!/usr/bin/env bats
# Specs for hooks/_lib/state-dir.sh — Cloud-safe per-install state directory.
# Replaces /tmp/claude-* markers with $HOME/.claude/state/* so concurrent Cloud
# sessions on one host cannot collide.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/state-dir.sh"
  TMP_DIR="$(mktemp -d)"
  SAVED_HOME="${HOME:-}"
  SAVED_STATE_DIR="${CLAUDE_STATE_DIR:-}"
}

teardown() {
  rm -rf "$TMP_DIR"
  export HOME="$SAVED_HOME"
  if [[ -n "$SAVED_STATE_DIR" ]]; then
    export CLAUDE_STATE_DIR="$SAVED_STATE_DIR"
  else
    unset CLAUDE_STATE_DIR
  fi
}

@test "H3.1 _state_dir default is \$HOME/.claude/state" {
  export HOME="$TMP_DIR"
  unset CLAUDE_STATE_DIR
  run bash -c "source '$LIB'; _state_dir"
  [ "$status" -eq 0 ]
  [ "$output" = "$TMP_DIR/.claude/state" ]
}

@test "H3.2 CLAUDE_STATE_DIR override wins over \$HOME-derived default" {
  export HOME="$TMP_DIR"
  export CLAUDE_STATE_DIR="$TMP_DIR/alt-state"
  run bash -c "source '$LIB'; _state_dir"
  [ "$status" -eq 0 ]
  [ "$output" = "$TMP_DIR/alt-state" ]
}

@test "H3.3 _state_path joins state dir with the given name" {
  export HOME="$TMP_DIR"
  unset CLAUDE_STATE_DIR
  run bash -c "source '$LIB'; _state_path 'ctx-percent'"
  [ "$status" -eq 0 ]
  [ "$output" = "$TMP_DIR/.claude/state/ctx-percent" ]
}

@test "H3.4 _ensure_state_dir creates the state directory if missing" {
  export HOME="$TMP_DIR"
  unset CLAUDE_STATE_DIR
  [ ! -d "$TMP_DIR/.claude/state" ]
  run bash -c "source '$LIB'; _ensure_state_dir"
  [ "$status" -eq 0 ]
  [ -d "$TMP_DIR/.claude/state" ]
}

#!/usr/bin/env bats
# Specs for hooks/_lib/state-dir.sh — Cloud-safe per-install state directory.
# Replaces /tmp/claude-* markers with $HOME/.claude/state/* so concurrent Cloud
# sessions on one host cannot collide.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/hooks/_lib/state-dir.sh"
  TMP_DIR="$(mktemp -d)"
  if [[ -n "${HOME+x}" ]]; then
    _PRIOR_HOME_SET=1; _PRIOR_HOME_VAL="$HOME"
  else
    _PRIOR_HOME_SET=0
  fi
  if [[ -n "${CLAUDE_STATE_DIR+x}" ]]; then
    _PRIOR_STATE_DIR_SET=1; _PRIOR_STATE_DIR_VAL="$CLAUDE_STATE_DIR"
  else
    _PRIOR_STATE_DIR_SET=0
  fi
  unset CLAUDE_STATE_DIR
}

teardown() {
  rm -rf "$TMP_DIR"
  if [[ "$_PRIOR_HOME_SET" = "1" ]]; then
    export HOME="$_PRIOR_HOME_VAL"
  else
    unset HOME
  fi
  if [[ "$_PRIOR_STATE_DIR_SET" = "1" ]]; then
    export CLAUDE_STATE_DIR="$_PRIOR_STATE_DIR_VAL"
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

_stat_mode() {
  # Linux (stat -c) first; macOS (stat -f) fallback. `stat -f` on Linux does
  # NOT fail cleanly (it means filesystem), so it must not be tried first.
  stat -c %a "$1" 2>/dev/null || stat -f %A "$1"
}

@test "H3.4a _ensure_state_dir creates directory with mode 0700 (no TOCTOU window)" {
  export HOME="$TMP_DIR"
  unset CLAUDE_STATE_DIR
  run bash -c "source '$LIB'; _ensure_state_dir"
  [ "$status" -eq 0 ]
  mode=$(_stat_mode "$TMP_DIR/.claude/state")
  [ "$mode" = "700" ]
}

@test "H3.4b _state_write writes file with mode 0600 (umask-hardened)" {
  export HOME="$TMP_DIR"
  unset CLAUDE_STATE_DIR
  run bash -c "source '$LIB'; _ensure_state_dir; echo content | _state_write 'marker'"
  [ "$status" -eq 0 ]
  mode=$(_stat_mode "$TMP_DIR/.claude/state/marker")
  [ "$mode" = "600" ]
  [ "$(cat "$TMP_DIR/.claude/state/marker")" = "content" ]
}

@test "H3.5 _state_read echoes the content written by _state_write" {
  export HOME="$TMP_DIR"
  unset CLAUDE_STATE_DIR
  run bash -c "source '$LIB'; _ensure_state_dir; printf 'PAIR\n' | _state_write 'gear-123'; _state_read 'gear-123'"
  [ "$status" -eq 0 ]
  [ "$output" = "PAIR" ]
}

@test "H3.6 _state_read on a missing marker fails without printing anything" {
  export HOME="$TMP_DIR"
  unset CLAUDE_STATE_DIR
  run bash -c "source '$LIB'; _ensure_state_dir; _state_read 'does-not-exist'"
  [ "$status" -ne 0 ]
  [ -z "$output" ]
}

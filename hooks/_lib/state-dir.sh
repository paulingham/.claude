#!/usr/bin/env bash
# Per-install state directory for hooks — replaces /tmp/claude-* markers.
# Source this file; call _state_dir (ensures + echoes) or _state_path NAME.
# Honours CLAUDE_STATE_DIR override for hermetic tests.

_state_dir() {
  local dir="${CLAUDE_STATE_DIR:-$HOME/.claude/state}"
  echo "$dir"
}

_state_path() {
  local dir; dir=$(_state_dir)
  echo "$dir/$1"
}

_ensure_state_dir() {
  local dir; dir=$(_state_dir)
  mkdir -p -m 700 "$dir" 2>/dev/null || return 1
}

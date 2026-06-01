#!/usr/bin/env bash
# Per-install state directory for hooks — replaces /tmp/claude-* markers.
# Source this file; call _state_dir (ensures + echoes) or _state_path NAME.
# Honours CLAUDE_STATE_DIR override for hermetic tests.

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"
_state_dir() {
  local dir="${CLAUDE_STATE_DIR:-$HARNESS_DATA/state}"
  echo "$dir"
}

_state_path() {
  local dir; dir=$(_state_dir)
  echo "$dir/$1"
}

_ensure_state_dir() {
  local dir; dir=$(_state_dir)
  (umask 077 && mkdir -p "$dir") || return 1
}

_state_write() {
  local name="$1"
  ( umask 077 && cat > "$(_state_path "$name")" )
}

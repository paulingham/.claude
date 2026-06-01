#!/usr/bin/env bash
# Version pin check helper (sourced by session-start-bootstrap.sh)
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"

_ssvc_pin_path() { echo "$HARNESS_ROOT/version-pin"; }

_ssvc_check_version() {
  local pin_file pinned running bad
  pin_file=$(_ssvc_pin_path)
  [[ -f "$pin_file" ]] || return 0
  pinned=$(cat "$pin_file" | tr -d '[:space:]')
  running=${CLAUDE_VERSION:-$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)}
  [[ -n "$running" && "$pinned" != "$running" ]] || return 0
  echo "VERSION DRIFT: pinned=${pinned} running=${running}" >&2
  bad="$HARNESS_ROOT/knowledge/claude-code-known-bad-versions.md"
  [[ -f "$bad" ]] && cat "$bad" >&2 || true
}

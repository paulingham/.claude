#!/usr/bin/env bash
# Pairing + cursor helpers for worktree-cwd-check. Sourced by the hook only.
# Functions assume SESSION, TASK_ID, _wcc_emit_record are already in scope.

_wcc_confirm_lines() {
  local log="$1"; while IFS= read -r line; do
    [[ "$(echo "$line" | jq -r '.source // empty')" == "prevented" ]] && _wcc_emit_record "post-confirmed" >> "$log"
  done
}

_wcc_read_cursor() {
  local raw; raw=$(cat "$1" 2>/dev/null || echo 0)
  [[ "$raw" =~ ^[0-9]+$ ]] && printf '%s' "$raw" || printf '0'
}

_wcc_pair_prevented() {
  local cursor; cursor=$(_wcc_read_cursor "$1")
  local total; total=$(wc -l < "$2" 2>/dev/null | tr -d ' ')
  [[ "$total" -le "$cursor" ]] && return 0
  tail -n +$((cursor+1)) "$2" 2>/dev/null | _wcc_confirm_lines "$2"
  printf '%s' "$total" > "$1"
}

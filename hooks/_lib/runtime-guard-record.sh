#!/usr/bin/env bash
# Mode A — record subagent start time. Idempotent (preserves first-seen ts).
# Bash-3.2 clean. Source after runtime-guard-key.sh.

_rg_class_of() {
  local team="$1"
  [ -n "$team" ] && echo "teammate" || echo "subagent"
}

_rg_write_start() {
  local dir="$1" key="$2" class="$3" display="$4"
  local f="$dir/$key.start"
  [ -f "$f" ] && return 0
  mkdir -p "$dir" 2>/dev/null || return 0
  ( umask 077 && printf '%s:%s:%s\n' "$(date +%s)" "$class" "$display" > "$f" ) 2>/dev/null
}

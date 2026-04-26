#!/usr/bin/env bash
# Mode B — global scan of start files for over-cap subagents. Bash-3.2 clean.
# Source after resource-bounds.sh and runtime-guard-emit.sh.

_rg_cap_for_class() {
  case "$1" in teammate) _max_runtime_teammate ;; *) _max_runtime_subagent ;; esac
}

_rg_parse_start() {
  IFS=: read -r ts class disp < "$1" || return 1
  case "$ts" in ''|*[!0-9]*) return 1 ;; esac
  return 0
}

_rg_report_violation() {
  local f="$1" disp="$2" class="$3" elapsed="$4" cap="$5" key
  key="$(basename "$f" .start)"
  _rg_emit_block "$disp" "$class" "$elapsed" "$cap"
  _rg_log_violation "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$key" "$disp" "$class" "$elapsed" "$cap"
}

_rg_check_one() {
  local f="$1" now="$2" ts class disp elapsed cap
  _rg_parse_start "$f" || return 0
  elapsed=$((now - ts)); cap=$(_rg_cap_for_class "$class")
  [ "$elapsed" -le "$cap" ] && return 0
  _rg_report_violation "$f" "$disp" "$class" "$elapsed" "$cap"; return 1
}

_rg_scan_dir() {
  local dir="$1" now found=0
  [ -d "$dir" ] || return 0
  now=$(date +%s)
  for f in "$dir"/*.start; do
    [ -e "$f" ] || continue
    _rg_check_one "$f" "$now" || found=1
  done
  return "$found"
}

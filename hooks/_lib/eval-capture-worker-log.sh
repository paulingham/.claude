#!/usr/bin/env bash
# Capture-log writer. One log file per (timestamp, pr) for audit.

_ecw_log_dir()  { printf '%s' "eval/runs/.capture-log"; }
_ecw_log_ts()   { date -u +"%Y%m%dT%H%M%SZ"; }
_ecw_log_path() { printf '%s/%s-pr%s.log' "$(_ecw_log_dir)" "$(_ecw_log_ts)" "$1"; }

ecw_log() {
  local pr="$1" status="$2" msg="$3"
  mkdir -p "$(_ecw_log_dir)"
  printf '%s pr=%s status=%s msg=%s\n' "$(_ecw_log_ts)" "$pr" "$status" "$msg" \
    >> "$(_ecw_log_path "$pr")"
}

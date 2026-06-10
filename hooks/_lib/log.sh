#!/usr/bin/env bash
# Structured JSONL telemetry helper. API: _log_hook_start, _log_hook_trigger STR, log_hook_event EXIT.
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"
if [[ "${CLAUDE_HOOK_LOG_ENABLED:-1}" == "0" ]]; then
  _log_hook_start() { :; }; _log_hook_trigger() { :; }; log_hook_event() { :; }
  return 0 2>/dev/null
fi

_log_hook_start() {
  _LOG_HOOK_START="${EPOCHREALTIME:-0}"   # capture FIRST, before any work
  local src="${BASH_SOURCE[1]:-unknown}"
  src="${src##*/}"                        # pure bash basename
  _LOG_HOOK_NAME="${src%.sh}"             # strip .sh suffix
  _LOG_HOOK_TRIGGER="unknown"
}

_log_hook_trigger() { _LOG_HOOK_TRIGGER="$1"; }

_log_diff_us() {
  local s0="$1" f0="$2" s1="$3" f1="$4"
  local dus=$(( 10#$f1 - 10#$f0 ))
  local ds=$(( s1 - s0 ))
  (( dus < 0 )) && { dus=$(( dus + 1000000 )); ds=$(( ds - 1 )); }
  echo $(( ds * 1000 + dus / 1000 ))
}

_log_duration_ms() {
  local now="${EPOCHREALTIME:-0}" f0 f1
  [[ "$_LOG_HOOK_START" == "0" || "$now" == "0" ]] && { echo 0; return; }
  f0="${_LOG_HOOK_START##*.}000000"; f1="${now##*.}000000"
  _log_diff_us "${_LOG_HOOK_START%%.*}" "${f0:0:6}" "${now%%.*}" "${f1:0:6}"
}

_log_session_id() {
  local raw="${CLAUDE_SESSION_ID:-}"
  raw="${raw//[^A-Za-z0-9_-]/}"           # alphanumeric, underscore, hyphen — NO dots (path-traversal guard)
  [[ -z "$raw" ]] && raw="local-$$"
  echo "$raw"
}

_log_timestamp() { printf '%(%Y-%m-%dT%H:%M:%SZ)T' -1 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ; }

_log_sanitize() {
  local v="${1//\\/}"   # strip backslashes first (so we don't reintroduce escapes)
  v="${v//\"/}"         # strip double-quotes (JSON-injection guard)
  echo "$v"
}

_log_subagent_field() {
  local raw="$1"
  [ -z "$raw" ] && return 0
  printf ',"subagent_type":"%s"' "$(_log_sanitize "$raw")"
}

log_hook_event() {
  local ec="${1:-0}" stype="${2:-}" sid dur ts dir hn trig s extra
  sid="$(_log_session_id)"; dur="$(_log_duration_ms)"; ts="$(_log_timestamp)"
  hn="$(_log_sanitize "$_LOG_HOOK_NAME")"
  trig="$(_log_sanitize "$_LOG_HOOK_TRIGGER")"
  s="$(_log_sanitize "$sid")"
  extra="$(_log_subagent_field "$stype")"
  dir="${CLAUDE_HOOK_LOG_DIR:-$HARNESS_DATA/metrics}/$sid"; mkdir -p "$dir" 2>/dev/null || return 0
  printf '{"timestamp":"%s","hook_name":"%s","trigger":"%s","duration_ms":%d,"exit_code":%d,"session_id":"%s"%s}\n' \
    "$ts" "$hn" "$trig" "$dur" "$ec" "$s" "$extra" >> "$dir/hooks.jsonl" 2>/dev/null
}

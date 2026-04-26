#!/usr/bin/env bash
# Portable timeout wrapper. Uses `timeout` if available (GNU coreutils / gtimeout),
# otherwise falls back to a bash-native background+kill implementation.
# Returns 124 on timeout (GNU convention) so callers can map to `failed_timeout`.

run_with_timeout() {
  local seconds="$1"; shift
  if command -v timeout >/dev/null 2>&1; then timeout "$seconds" "$@"; return; fi
  if command -v gtimeout >/dev/null 2>&1; then gtimeout "$seconds" "$@"; return; fi
  _bash_timeout "$seconds" "$@"
}

_bash_timeout() {
  local seconds="$1"; shift
  "$@" & local pid=$!
  _watchdog "$pid" "$seconds" & local wd=$!
  wait "$pid" 2>/dev/null; local rc=$?
  _reap_watchdog "$wd"
  _normalise_rc "$rc"
}

_reap_watchdog() { kill "$1" 2>/dev/null; wait "$1" 2>/dev/null; }
_normalise_rc()  { [ "$1" -eq 143 ] && return 124; return "$1"; }

_watchdog() {
  local pid="$1"; local seconds="$2"
  sleep "$seconds"
  kill -TERM "$pid" 2>/dev/null
}

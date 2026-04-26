#!/usr/bin/env bash
# await-pattern-lib.sh — pure functions for log-pattern awaiting.
# Public: await_pattern <log> <regex> <timeout> <max_lines>
# Helpers: _aw_validate_args, _aw_resolve_metrics_path, _aw_strip_ansi.
# Exit codes: 0=match, 124=timeout, 130=SIGINT, 1=bad args/missing log/max_lines.

_aw_is_int() { case "$1" in ''|*[!0-9-]*) return 1;; -*) return 1;; *) return 0;; esac; }

_aw_validate_args() {
  [ "$#" -eq 4 ] || { echo "usage: await-pattern.sh <log_path> <regex> <timeout_seconds> <max_lines>" >&2; return 1; }
  _aw_is_int "$3" && _aw_is_int "$4" || { echo "timeout_seconds and max_lines must be non-negative integers" >&2; return 1; }
}

_aw_validate_log_path() {
  [ -f "$1" ] || { echo "log_path not found: $1" >&2; return 1; }
}

_aw_resolve_metrics_path() {
  local sid="${CLAUDE_SESSION_ID:-local-$$}" dir
  dir="$HOME/.claude/metrics/$sid"; mkdir -p "$dir" 2>/dev/null
  echo "$dir/await-events.jsonl"
}

_aw_strip_ansi() { sed -E $'s/\x1B\\[[0-9;]*[A-Za-z]//g'; }

_aw_now_ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

#!/usr/bin/env bash
# session-name.sh — name helpers for new-session.sh.
# _default_name: YYYYMMDD-HHMMSS-<4-char hostname slug> in UTC.
# _validate_name: rejects empty, slashes, whitespace.

_hostname_slug() {
  local s; s="$(hostname 2>/dev/null | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9')"
  [[ ${#s} -lt 4 ]] && s="${s}xxxx"
  printf '%s' "${s: -4}"
}

_default_name() {
  printf '%s-%s\n' "$(date -u +%Y%m%d-%H%M%S)" "$(_hostname_slug)"
}

_validate_name() {
  [[ -n "$1" && "$1" != *[[:space:]/]* ]]
}

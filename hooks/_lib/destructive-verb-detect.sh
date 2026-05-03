#!/usr/bin/env bash
# Destructive-verb detection — sourced by hooks/main-branch-guard.sh.
# Wave 2 / A4 closes PocketOS Apr 27 2026 incident: LLM-blessed destructive
# command shipped without a non-LLM confirmation gate. This module provides
# that gate.
#
# Contract:
#   is_destructive_command "$cmd"          → 0 if matches a verb in destructive-verbs.txt
#   destructive_confirm_active             → 0 if CLAUDE_DESTRUCTIVE_CONFIRM is set
#                                             AND CLAUDE_DESTRUCTIVE_CONFIRM_TS is within
#                                             the last 600 seconds (configurable via
#                                             CLAUDE_DESTRUCTIVE_CONFIRM_TTL)
#   destructive_block_message "$cmd"       → prints user-facing block text on stderr
#
# Bash 3.2 SAFE: ERE only, no PCRE. No mapfile/readarray.

_DV_VERBS_FILE_DEFAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/destructive-verbs.txt"

_dv_verbs_file() {
  printf '%s' "${CLAUDE_DESTRUCTIVE_VERBS_FILE:-$_DV_VERBS_FILE_DEFAULT}"
}

_dv_load_patterns() {
  local f; f=$(_dv_verbs_file)
  [[ -r "$f" ]] || return 1
  awk 'NF && $1 !~ /^#/' "$f"
}

is_destructive_command() {
  local cmd="$1" line
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$cmd" =~ $line ]] && return 0
  done < <(_dv_load_patterns)
  return 1
}

destructive_confirm_active() {
  local token="${CLAUDE_DESTRUCTIVE_CONFIRM:-}"
  local ts="${CLAUDE_DESTRUCTIVE_CONFIRM_TS:-}"
  local ttl="${CLAUDE_DESTRUCTIVE_CONFIRM_TTL:-600}"
  [[ "$token" == "I-have-a-restorable-backup-elsewhere" ]] || return 1
  [[ -z "$ts" ]] && return 1
  case "$ts" in ''|*[!0-9]*) return 1 ;; esac
  case "$ttl" in ''|*[!0-9]*) ttl=600 ;; esac
  local now; now=$(date +%s 2>/dev/null) || return 1
  (( now - ts <= ttl )) || return 1
  return 0
}

destructive_block_message() {
  local cmd="$1"
  printf 'BLOCKED: destructive verb detected without confirmation token.\n' >&2
  printf '  command: %s\n' "$cmd" >&2
  printf 'Set CLAUDE_DESTRUCTIVE_CONFIRM=I-have-a-restorable-backup-elsewhere\n' >&2
  printf 'AND CLAUDE_DESTRUCTIVE_CONFIRM_TS=$(date +%%s) within the last 600 seconds.\n' >&2
  printf 'See rules/agent-protocol.md > Non-LLM Gates on Destructive Verbs.\n' >&2
}

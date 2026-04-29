#!/usr/bin/env bash
# Resource bounds resolver — single source of truth for depth + runtime caps.
# Defaults: depth=3, subagent=1800s, teammate=3600s. Bash-3.2 clean.
# Source this lib; call _max_depth, _max_runtime_subagent, _max_runtime_teammate.

_resolve_int() {
  local value="$1" fallback="$2"
  case "$value" in
    ''|*[!0-9]*) echo "$fallback" ;;
    *) echo "$value" ;;
  esac
}

_max_depth() {
  _resolve_int "${CLAUDE_SUBAGENT_MAX_DEPTH:-}" 3
}

_max_runtime_subagent() {
  _resolve_int "${CLAUDE_SUBAGENT_MAX_RUNTIME:-}" 1800
}

_max_runtime_teammate() {
  _resolve_int "${CLAUDE_TEAMMATE_MAX_RUNTIME:-}" 3600
}

_max_respawn_count() {
  _resolve_int "${CLAUDE_SUBAGENT_MAX_RESPAWN:-}" 3
}

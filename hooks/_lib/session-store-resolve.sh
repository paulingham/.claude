#!/usr/bin/env bash
# Backend resolution + warning helper. Caches answer in exported shell var
# _SESSION_STORE_RESOLVED_BACKEND (process-scoped; never a file sentinel).

_session_store_lib_dir() { dirname "${BASH_SOURCE[0]}"; }
_session_store_repo_root() { cd "$(_session_store_lib_dir)/../.." && pwd; }

_session_store_warn() {
  printf '[session-store] %s backend selected but %s — falling back to local\n' "$1" "$2" >&2
  local lib; lib="$(_session_store_lib_dir)"
  local input='{"tool_input":{"subagent_type":"session-store"}}'
  local resolved; resolved=$(printf '{"requested":"%s","reason":"%s","resolved":"local"}' "$1" "$2")
  bash "$lib/log-injection.sh" "$input" "$resolved" "session-store-fallback" "session-store-mirror.jsonl" 2>/dev/null || true
}

_resolve_check_s3() {
  command -v aws >/dev/null 2>&1 || { _session_store_warn s3 "'aws' CLI not found"; return 1; }
  [[ -n "${CLAUDE_SESSION_STORE_BUCKET:-}" ]] || { _session_store_warn s3 "CLAUDE_SESSION_STORE_BUCKET not set"; return 1; }
}

_resolve_check_redis() {
  command -v redis-cli >/dev/null 2>&1 || { _session_store_warn redis "'redis-cli' not found"; return 1; }
  [[ -n "${CLAUDE_SESSION_STORE_REDIS_URL:-}" ]] || { _session_store_warn redis "CLAUDE_SESSION_STORE_REDIS_URL not set"; return 1; }
}

_resolve_pick() {
  local req="${CLAUDE_SESSION_STORE_BACKEND:-local}"
  [[ "$req" = "local" ]] && { echo local; return; }
  [[ "$req" = "s3"    ]] && { _resolve_check_s3    && echo s3    || echo local; return; }
  [[ "$req" = "redis" ]] && { _resolve_check_redis && echo redis || echo local; return; }
  echo local
}

_resolve_backend() {
  [[ -n "${_SESSION_STORE_RESOLVED_BACKEND:-}" ]] && { echo "$_SESSION_STORE_RESOLVED_BACKEND"; return; }
  export _SESSION_STORE_RESOLVED_BACKEND; _SESSION_STORE_RESOLVED_BACKEND=$(_resolve_pick)
  echo "$_SESSION_STORE_RESOLVED_BACKEND"
}

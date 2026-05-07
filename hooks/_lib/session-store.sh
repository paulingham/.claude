#!/usr/bin/env bash
# Session-store contract dispatcher. Sources resolve + sync helpers + per-backend adapters.
# Each contract fn is ≤ 8 lines; file ≤ 50 lines.

_SESSION_STORE_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SESSION_STORE_ROOT="$(cd "$_SESSION_STORE_LIB/../.." && pwd)"

# shellcheck source=/dev/null
source "$_SESSION_STORE_LIB/session-store-resolve.sh"
# shellcheck source=/dev/null
source "$_SESSION_STORE_ROOT/session-memory/adapters/local.sh"
# shellcheck source=/dev/null
source "$_SESSION_STORE_ROOT/session-memory/adapters/s3.sh"
# shellcheck source=/dev/null
source "$_SESSION_STORE_ROOT/session-memory/adapters/redis.sh"
# shellcheck source=/dev/null
source "$_SESSION_STORE_LIB/session-store-sync.sh"
# shellcheck source=/dev/null
source "$_SESSION_STORE_LIB/session-memory-read-split.sh"

_session_store_validate_key() {
  local k
  for k in "$@"; do
    [[ -z "$k" || "$k" == */* || "$k" == *..* || "$k" == .* ]] && return 1
  done
  return 0
}

_session_store_call() {
  local backend op="$1"; shift; backend=$(_resolve_backend)
  case "$backend" in
    s3|redis) "_${backend}_$op" "$@" ;;
    *) "_local_$op" "$@" ;;
  esac
}

_session_store_dispatch() {
  local op="$1"; shift
  [[ "$op" != "list" ]] && { _session_store_validate_key "$1" "$2" || return 1; }
  _session_store_call "$op" "$@"
}

session_store_put()          { _session_store_dispatch put          "$@"; }
session_store_get()          { _session_store_dispatch get          "$@"; }
session_store_delete()       { _session_store_dispatch delete       "$@"; }
session_store_list()         { _session_store_dispatch list         "$@"; }
session_store_list_subkeys() { _session_store_dispatch list_subkeys "$@"; }

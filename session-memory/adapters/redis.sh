#!/usr/bin/env bash
# Redis adapter — Slice 3 stub; bodies filled in cycle 3.
_redis_key() {
  local prefix="${CLAUDE_SESSION_STORE_PREFIX:-sessions/}"
  printf '%s%s:%s\n' "$prefix" "$1" "$2"
}
_redis_put()          { return 1; }
_redis_get()          { return 1; }
_redis_delete()       { return 1; }
_redis_list()         { return 0; }
_redis_list_subkeys() { return 1; }

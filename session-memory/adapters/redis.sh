#!/usr/bin/env bash
# Redis adapter. Shells out to `redis-cli SET/GET/DEL/KEYS`.

_redis_key() {
  local prefix="${CLAUDE_SESSION_STORE_PREFIX:-sessions/}"
  printf '%s%s:%s\n' "$prefix" "$1" "$2"
}

_redis_put() {
  local key; key=$(_redis_key "$1" "$2")
  [[ "$3" = "-" ]] && { redis-cli -u "$CLAUDE_SESSION_STORE_REDIS_URL" -x SET "$key" >/dev/null 2>&1; return; }
  redis-cli -u "$CLAUDE_SESSION_STORE_REDIS_URL" -x SET "$key" < "$3" >/dev/null 2>&1
}

_redis_get() {
  local key exists
  key=$(_redis_key "$1" "$2")
  exists=$(redis-cli -u "$CLAUDE_SESSION_STORE_REDIS_URL" EXISTS "$key" 2>/dev/null) || return 1
  [[ "$exists" = "1" ]] || return 1
  redis-cli -u "$CLAUDE_SESSION_STORE_REDIS_URL" GET "$key" 2>/dev/null
}

_redis_delete() {
  local key; key=$(_redis_key "$1" "$2")
  redis-cli -u "$CLAUDE_SESSION_STORE_REDIS_URL" DEL "$key" >/dev/null 2>&1 || return 0
}

_redis_list() {
  local prefix="${CLAUDE_SESSION_STORE_PREFIX:-sessions/}"
  redis-cli -u "$CLAUDE_SESSION_STORE_REDIS_URL" KEYS "${prefix}*" 2>/dev/null \
    | awk -F: -v p="$prefix" '{ sub("^"p,"",$1); print $1 }' | sort -u
}

_redis_list_subkeys() {
  local blob; blob=$(_redis_get "$1" "$2") || return 1
  printf '%s\n' "$blob" | awk '/^# / { sub(/^# /, ""); print }'
}

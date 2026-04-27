#!/usr/bin/env bash
# Redis adapter. Credentials in URL are stripped and passed via REDISCLI_AUTH.

_redis_init() {
  [[ -n "$_REDIS_URL_STRIPPED" ]] && return 0
  local url="$CLAUDE_SESSION_STORE_REDIS_URL" creds rest
  if [[ "$url" == *"@"* && "$url" == *"://"* ]]; then
    rest="${url#*://}"; creds="${rest%@*}"; rest="${rest#*@}"
    export REDISCLI_AUTH="${creds#*:}"; _REDIS_URL_STRIPPED="${url%%://*}://${rest}"
  else _REDIS_URL_STRIPPED="$url"; fi
}

_redis_cli() { _redis_init; redis-cli -u "$_REDIS_URL_STRIPPED" "$@"; }
_redis_key() { printf '%s%s:%s\n' "${CLAUDE_SESSION_STORE_PREFIX:-sessions/}" "$1" "$2"; }

_redis_put() {
  local key; key=$(_redis_key "$1" "$2")
  [[ "$3" = "-" ]] && { _redis_cli -x SET "$key" >/dev/null 2>&1; return; }
  _redis_cli -x SET "$key" < "$3" >/dev/null 2>&1
}

_redis_get() {
  local key exists; key=$(_redis_key "$1" "$2")
  exists=$(_redis_cli EXISTS "$key" 2>/dev/null) || return 1
  [[ "$exists" = "1" ]] || return 1
  _redis_cli GET "$key" 2>/dev/null
}

_redis_delete() {
  local key; key=$(_redis_key "$1" "$2")
  _redis_cli DEL "$key" >/dev/null 2>&1 || return 0
}

_redis_list() {
  local p="${CLAUDE_SESSION_STORE_PREFIX:-sessions/}"
  _redis_cli KEYS "${p}*" 2>/dev/null | awk -F: -v p="$p" '{ sub("^"p,"",$1); print $1 }' | sort -u
}

_redis_list_subkeys() {
  local blob; blob=$(_redis_get "$1" "$2") || return 1
  printf '%s\n' "$blob" | awk '/^# / { sub(/^# /, ""); print }'
}

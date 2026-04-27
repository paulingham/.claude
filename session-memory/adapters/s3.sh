#!/usr/bin/env bash
# S3 adapter. Shells out to `aws s3 cp/ls/rm`. Whole-blob writes (no append).

_s3_uri() {
  local prefix="${CLAUDE_SESSION_STORE_PREFIX:-sessions/}"
  printf 's3://%s/%s%s/%s\n' "${CLAUDE_SESSION_STORE_BUCKET}" "$prefix" "$1" "$2"
}

_s3_put() {
  local uri; uri=$(_s3_uri "$1" "$2")
  [[ "$3" = "-" ]] && { aws s3 cp - "$uri" >/dev/null 2>&1; return; }
  aws s3 cp "$3" "$uri" >/dev/null 2>&1
}

_s3_get() {
  local uri; uri=$(_s3_uri "$1" "$2")
  aws s3 cp "$uri" - 2>/dev/null
}

_s3_delete() {
  local uri; uri=$(_s3_uri "$1" "$2")
  aws s3 rm "$uri" >/dev/null 2>&1 || return 0
}

_s3_list() {
  local prefix="${CLAUDE_SESSION_STORE_PREFIX:-sessions/}"
  local uri="s3://${CLAUDE_SESSION_STORE_BUCKET}/$prefix"
  aws s3 ls "$uri" 2>/dev/null | awk '/^ *PRE / { sub(/\/$/,"",$2); print $2 }' | sort
}

_s3_list_subkeys() {
  local blob; blob=$(_s3_get "$1" "$2") || return 1
  [[ -z "$blob" ]] && return 1
  printf '%s\n' "$blob" | awk '/^# / { sub(/^# /, ""); print }'
}

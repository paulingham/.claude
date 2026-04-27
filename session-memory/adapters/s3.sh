#!/usr/bin/env bash
# S3 adapter — Slice 2 stub; bodies filled in cycle 2.
_s3_uri() {
  local prefix="${CLAUDE_SESSION_STORE_PREFIX:-sessions/}"
  printf 's3://%s/%s%s/%s\n' "${CLAUDE_SESSION_STORE_BUCKET}" "$prefix" "$1" "$2"
}
_s3_put()          { return 1; }
_s3_get()          { return 1; }
_s3_delete()       { return 1; }
_s3_list()         { return 0; }
_s3_list_subkeys() { return 1; }

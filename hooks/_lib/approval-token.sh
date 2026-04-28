#!/usr/bin/env bash
# Approval token library — Wave 4-N
# Source this file; call _at_* functions.

_at_token_path() {
  echo "$HOME/.claude/pipeline-state/$1-approval.token"
}

_at_resolve_task_id() {
  local segment="${1##*/}"
  [ -z "$segment" ] || [ "$segment" = "main" ] || [ "$segment" = "master" ] && return 0
  echo "$segment"
}

_at_pipeline_active() {
  [ -f "$HOME/.claude/pipeline-state/$1-pipeline.md" ]
}

_at_token_exists() {
  [ -f "$(_at_token_path "$1")" ]
}

_at_token_verdict() {
  local path; path="$(_at_token_path "$1")"
  [ -f "$path" ] || { echo "MISSING"; return 0; }
  jq -r '.verdict // ""' "$path" 2>/dev/null || echo ""
}

_at_write_token() {
  local task_id="$1" verdict="$2" path; path="$(_at_token_path "$task_id")"
  printf '{"verdict":"%s","timestamp":"%s","signer":"product-acceptance"}\n' \
    "$verdict" "$(date -u +%FT%TZ)" > "$path"
}

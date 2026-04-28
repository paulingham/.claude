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

_at_valid_verdict() {
  case "$1" in APPROVED|APPROVED_WITH_CONDITIONS|REJECTED) return 0 ;; *) return 1 ;; esac
}

_at_write_token() {
  _at_valid_verdict "$2" || return 1
  printf '{"verdict":"%s","timestamp":"%s","signer":"product-acceptance"}\n' \
    "$2" "$(date -u +%FT%TZ)" > "$(_at_token_path "$1")"
}

_at_log_blocked() {
  local task_id="$1" reason="$2"
  local dir="$HOME/.claude/metrics/${CLAUDE_SESSION_ID:-no-session}"
  mkdir -p "$dir"
  printf '{"ts":"%s","task_id":"%s","reason":"%s"}\n' "$(date -u +%FT%TZ)" "$task_id" "$reason" >> "$dir/pr-blocked.jsonl"
}

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
  # Validate task_id to prevent path traversal
  [[ "$1" =~ ^[A-Za-z0-9_.-]+$ ]] || return 1
  _at_valid_verdict "$2" || return 1
  printf '{"verdict":"%s","timestamp":"%s","signer":"product-acceptance"}\n' \
    "$2" "$(date -u +%FT%TZ)" > "$(_at_token_path "$1")"
}

_at_emit_jsonl() {
  python3 -c 'import json,sys; print(json.dumps({"ts":sys.argv[1],"task_id":sys.argv[2],"reason":sys.argv[3]}))' "$@"
}

_at_log_blocked() {
  local raw="${CLAUDE_SESSION_ID:-no-session}"
  local safe="${raw//[^A-Za-z0-9_-]/_}"
  local dir="$HOME/.claude/metrics/${safe}"
  mkdir -p "$dir"
  _at_emit_jsonl "$(date -u +%FT%TZ)" "$1" "$2" >> "$dir/pr-blocked.jsonl"
}

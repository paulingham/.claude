#!/usr/bin/env bash
# Approval token library — Wave 4-N. ABI FROZEN; only path resolution changes
# during DUAL_PATH soak. Read precedence: existing file wins; on collision,
# fresher mtime wins. Writes go to NEW layout only.
# shellcheck source=pipeline-state-paths.sh
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"
source "$(dirname "${BASH_SOURCE[0]}")/pipeline-state-paths.sh"

_at_legacy_token_path() { echo "$HARNESS_DATA/pipeline-state/$1-approval.token"; }
_at_new_token_path()    { echo "$HARNESS_DATA/pipeline-state/$1/approval.token"; }

_at_token_path() {
  local l n; l=$(_at_legacy_token_path "$1"); n=$(_at_new_token_path "$1")
  if [ -f "$l" ] && [ ! -f "$n" ]; then echo "$l"
  elif [ -f "$n" ] && [ ! -f "$l" ]; then echo "$n"
  elif [ -f "$l" ] && [ -f "$n" ] && [ "$l" -nt "$n" ]; then echo "$l"
  else echo "$n"
  fi
}

_at_resolve_task_id() {
  local segment="${1##*/}"
  [ -z "$segment" ] || [ "$segment" = "main" ] || [ "$segment" = "master" ] && return 0
  echo "$segment"
}

_at_pipeline_active() {
  _psp_pipeline_active "$1"
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
  # Validate task_id to prevent path traversal. Writes go to NEW layout only.
  # First char MUST be alnum/underscore/hyphen — rejects '.' and '..' which
  # would resolve $HARNESS_DATA/pipeline-state/{task}/approval.token to a
  # parent directory landing pad.
  [[ "$1" =~ ^[A-Za-z0-9_-][A-Za-z0-9_.-]*$ ]] || return 1
  _at_valid_verdict "$2" || return 1
  local target; target=$(_at_new_token_path "$1")
  mkdir -p "$(dirname "$target")"
  printf '{"verdict":"%s","timestamp":"%s","signer":"product-acceptance"}\n' \
    "$2" "$(date -u +%FT%TZ)" > "$target"
}

_at_emit_jsonl() {
  python3 -c 'import json,sys; print(json.dumps({"ts":sys.argv[1],"task_id":sys.argv[2],"reason":sys.argv[3]}))' "$@"
}

_at_log_blocked() {
  local raw="${CLAUDE_SESSION_ID:-no-session}"
  local safe="${raw//[^A-Za-z0-9_-]/_}"
  local dir="$HARNESS_DATA/metrics/${safe}"
  mkdir -p "$dir"
  _at_emit_jsonl "$(date -u +%FT%TZ)" "$1" "$2" >> "$dir/pr-blocked.jsonl"
}

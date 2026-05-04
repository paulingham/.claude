#!/usr/bin/env bash
# Main-branch invariant guard — PreToolUse Bash hook.
# Refuses HEAD-mutating commands that lack an explicit delegation prefix.
# Profile=minimal so it ALWAYS runs (mirrors quality-gate, orchestrator-discipline).
# Recursion safety: hook executes only jq, mkdir, printf, date, cat, awk —
# none match the forbidden regex, so the hook cannot block its own subshells.
#
# enforces: rules/_detail/agent-protocol.md:Main-Branch Invariant
# protects: build-implementation, pr-creation

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Bash}"
trap 'log_hook_event $?' EXIT

set -uo pipefail

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "minimal" || exit 0
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/main-branch-detect.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/destructive-verb-detect.sh"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[[ "$TOOL_NAME" != "Bash" ]] && exit 0
[[ -z "$COMMAND" ]] && exit 0

_mbg_destructive_log() {
  local sid tid dir; sid="${CLAUDE_SESSION_ID:-local-$$}"; sid="${sid//[^a-zA-Z0-9_.-]/}"
  tid="${CLAUDE_PIPELINE_TASK_ID:-}"; dir="$HOME/.claude/metrics/${sid:-local-$$}"
  mkdir -p "$dir" 2>/dev/null || return 0
  jq -nc --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg sid "$sid" --arg tid "$tid" \
    --arg cmd "$(_mbg_redact "$COMMAND")" \
    '{timestamp:$ts,session_id:$sid,task_id:$tid,command:$cmd,source:"destructive-verb",action:"prevented"}' \
    >> "$dir/main-branch-violations.jsonl" 2>/dev/null || true
}

_mbg_redact() {
  printf '%s' "$1" | sed -E 's#(://)[^/@[:space:]]+:[^/@[:space:]]+@#\1REDACTED@#g'
}

if is_destructive_command "$COMMAND"; then
  if destructive_confirm_active; then
    : # confirmation token live within TTL — fall through to standard mbg checks
  else
    _mbg_destructive_log
    destructive_block_message "$(_mbg_redact "$COMMAND")"
    exit 2
  fi
fi

is_forbidden_command "$COMMAND" || exit 0

_mbg_emit_record() {
  jq -nc --arg ts "$1" --arg sid "$2" --arg tid "$3" --arg cmd "$(_mbg_redact "$COMMAND")" \
    '{timestamp:$ts,session_id:$sid,task_id:$tid,command:$cmd,source:"prevented",action:"prevented"}'
}

_mbg_log_violation() {
  local sid tid dir; sid="${CLAUDE_SESSION_ID:-local-$$}"; sid="${sid//[^a-zA-Z0-9_.-]/}"
  tid="${CLAUDE_PIPELINE_TASK_ID:-}"; dir="$HOME/.claude/metrics/${sid:-local-$$}"
  mkdir -p "$dir" 2>/dev/null || return 0
  _mbg_emit_record "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sid" "$tid" \
    >> "$dir/main-branch-violations.jsonl" 2>/dev/null || true
}

_mbg_print_block() {
  printf 'BLOCKED: REPO_ROOT HEAD must stay on `main`. The command:\n  %s\n' "$(_mbg_redact "$COMMAND")" >&2
  printf 'contains a HEAD-mutating clause without a delegation prefix.\n' >&2
  printf 'Use a delegation prefix: `cd "$WT" && ...`, `git -C "$WT" ...`, or `git --git-dir="$WT/.git" ...`\n' >&2
  printf 'See rules/agent-protocol.md > Main-Branch Invariant.\n' >&2
}

_mbg_log_violation
_mbg_print_block
exit 2

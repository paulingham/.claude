#!/usr/bin/env bash
# Main-branch invariant guard — PreToolUse Bash hook.
# Refuses HEAD-mutating commands that lack an explicit delegation prefix.
# Profile=minimal so it ALWAYS runs (mirrors quality-gate, orchestrator-discipline).
# Recursion safety: hook executes only jq, mkdir, printf, date, cat, awk —
# none match the forbidden regex, so the hook cannot block its own subshells.

set -uo pipefail

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "minimal" || exit 0
source ~/.claude/hooks/_lib/main-branch-detect.sh

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[[ "$TOOL_NAME" != "Bash" ]] && exit 0
[[ -z "$COMMAND" ]] && exit 0
is_forbidden_command "$COMMAND" || exit 0

_mbg_emit_record() {
  jq -nc --arg ts "$1" --arg sid "$2" --arg tid "$3" --arg cmd "$COMMAND" \
    '{timestamp:$ts,session_id:$sid,task_id:$tid,command:$cmd,source:"prevented",action:"prevented"}'
}

_mbg_log_violation() {
  local sid="${CLAUDE_SESSION_ID:-local-$$}" tid="${CLAUDE_PIPELINE_TASK_ID:-}" dir
  dir="$HOME/.claude/metrics/$sid"; mkdir -p "$dir" 2>/dev/null || return 0
  _mbg_emit_record "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$sid" "$tid" \
    >> "$dir/main-branch-violations.jsonl" 2>/dev/null || true
}

_mbg_print_block() {
  printf 'BLOCKED: REPO_ROOT HEAD must stay on `main`. The command:\n  %s\n' "$COMMAND" >&2
  printf 'contains a HEAD-mutating clause without a delegation prefix.\n' >&2
  printf 'Use one of: `git -C "$WORKTREE" ...`, `git --git-dir="$WORKTREE/.git" ...`,\n' >&2
  printf '`cd "$WORKTREE" && ...`, or `(cd "$WORKTREE" && ...)`.\n' >&2
  printf 'See rules/agent-protocol.md > Main-Branch Invariant.\n' >&2
}

_mbg_log_violation
_mbg_print_block
exit 2

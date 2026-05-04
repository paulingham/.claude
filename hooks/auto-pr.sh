#!/usr/bin/env bash
# Auto-PR Advisory Hook — Stop event
# Detects when a feature branch has commits ahead of main and suggests /pr-creation.
# Advisory only — never blocks. Suppresses suggestion when an active pipeline lacks a passing approval token.
#
# enforces: rules/_detail/pipeline-protocol.md:Phase Checklist
# protects: pr-creation

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "Stop"
trap 'log_hook_event $?' EXIT

set -uo pipefail
# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0
# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/auto-pr-preflight.sh"
# shellcheck source=/dev/null
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/approval-token.sh"

INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
[ "$STOP_HOOK_ACTIVE" = "true" ] && exit 0

BRANCH="$(_apf_resolve_branch)"; [ -z "$BRANCH" ] && exit 0
BASE_BRANCH="$(_apf_resolve_base)"; [ -z "$BASE_BRANCH" ] && exit 0
AHEAD="$(_apf_commits_ahead "$BASE_BRANCH")"; [ "$AHEAD" -eq 0 ] && exit 0
UNCOMMITTED="$(_apf_uncommitted_count)"; [ "$UNCOMMITTED" -gt 0 ] && exit 0

TASK_ID="$(_at_resolve_task_id "$BRANCH")"
TOKEN_DETAIL=""
if [ -n "$TASK_ID" ] && _at_pipeline_active "$TASK_ID"; then
  VERDICT="$(_at_token_verdict "$TASK_ID")"
  case "$VERDICT" in
    APPROVED|APPROVED_WITH_CONDITIONS) TOKEN_DETAIL=" Approval token: $VERDICT." ;;
    *) _at_log_blocked "$TASK_ID" "$VERDICT"; exit 0 ;;
  esac
fi

echo "AUTO-PR: Branch '${BRANCH}' has ${AHEAD} commit(s) ahead of ${BASE_BRANCH}.${TOKEN_DETAIL} Consider running /pr-creation."
exit 0

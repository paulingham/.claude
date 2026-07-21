#!/usr/bin/env bash
# PreToolUse hook: gear-aware AskUserQuestion gate.
# Blocks AskUserQuestion in BUILD/PIPELINE (autonomous) gear, ALLOWS it in PAIR
# gear where interactive questions are the point, and fails CLOSED (blocks) when
# the gear state is absent or unreadable.
# Reads JSON from stdin, checks tool_name, exits 2 to block when matched.
#
# enforces: rules/core.md:Iron Laws
# protects: pipeline
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:AskUserQuestion"
trap 'log_hook_event $?' EXIT

set -euo pipefail

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/gear-gate.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/session-id.sh"

payload="$(cat)"
# PAIR gear allows interactive questions; only autonomous gears block them.
check_gear_gate "$(resolve_session_id "$payload")" || { trap - EXIT; exit 0; }

tool_name="$(printf '%s' "$payload" | sed -n 's/.*"tool_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

if [ "$tool_name" = "AskUserQuestion" ]; then
  cat >&2 <<'MSG'
BLOCKED: AskUserQuestion is disabled in autonomous mode.
Self-resolve instead:
  1. Re-read the task and any relevant ~/.claude/rules/core.md, ~/.claude/protocols/, or memory/feedback_*.md.
  2. Check for a project default or the most conservative autonomous action.
  3. Decide and proceed. If work is genuinely blocked on a destructive or
     irreversible action, state the decision point in your final turn response
     — do not call AskUserQuestion.
MSG
  exit 2
fi

exit 0

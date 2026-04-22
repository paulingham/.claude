#!/usr/bin/env bash
# SubagentStart hook: write agent role to temp file for observation-capture.sh
# Runs in the orchestrator process BEFORE the subagent starts.
# observation-capture.sh reads this as fallback when env var is empty.
# For parallel agents: last-writer-wins (acceptable — parallel agents share phase).

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0
# shellcheck source=_lib/state-dir.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib/state-dir.sh"
_ensure_state_dir

INPUT=$(cat)
AGENT_TYPE=$(echo "$INPUT" | jq -r '.subagent_type // .agent_type // empty' 2>/dev/null)

if [[ -z "$AGENT_TYPE" ]]; then
    exit 0
fi

printf '%s\n' "$AGENT_TYPE" | _state_write "agent-role" 2>/dev/null || true

exit 0

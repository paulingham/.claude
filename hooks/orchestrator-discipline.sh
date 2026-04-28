#!/usr/bin/env bash
# Orchestrator Discipline Hook — PreToolUse hook for Write and Edit tools
#
# Blocks the orchestrator from writing source files directly.
# The orchestrator must delegate all file changes to agents via skills.
#
# ALLOW (by path): .md files, .claude/automation/, .claude/hooks/.
# ALLOW (by caller context): tool call originates from a subagent — harness injects
#   `subagent_type` into PreToolUse stdin JSON for every subagent tool call; the
#   orchestrator's own tool calls always have an empty subagent_type.
#   CWD-based worktree detection is kept as a fallback but is unreliable because
#   hooks run with the main session's CWD, not the subagent's CWD.
# BLOCK: everything else (this is the orchestrator writing from the main tree).

source ~/.claude/hooks/_lib/log.sh
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Write}"
trap 'log_hook_event $?' EXIT

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "minimal" || exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.subagent_type // empty')

is_path_allow_listed() {
    [[ -z "$1" || "$1" =~ \.md$ ]] && return 0
    [[ "$1" =~ \.claude/automation/ || "$1" =~ \.claude/hooks/ ]]
}

is_caller_a_subagent() {
    # Primary: harness injects subagent_type for every subagent tool call.
    # Empty = orchestrator's own call. Non-empty = delegated to an agent.
    [[ -n "$SUBAGENT_TYPE" ]] && return 0
    # Fallback: CWD-based worktree check (unreliable — hook CWD is the main
    # session CWD, not the agent CWD — but kept for belt-and-suspenders).
    local toplevel
    toplevel=$(git rev-parse --show-toplevel 2>/dev/null)
    [[ "$toplevel" == *"/.claude/worktrees/agent-"* ]] || [[ "$PWD" == *"/.claude/worktrees/agent-"* ]]
}

if is_path_allow_listed "$FILE_PATH"; then
    exit 0
fi

if is_caller_a_subagent; then
    exit 0
fi

echo "BLOCKED: Orchestrator cannot write source files directly. Delegate to an agent via the appropriate skill." >&2
exit 2

#!/usr/bin/env bash
# Orchestrator Discipline Hook — PreToolUse hook for Write and Edit tools
#
# Blocks the orchestrator from writing source files directly.
# The orchestrator must delegate all file changes to agents via skills.
#
# ALLOW (by path): .md files, .claude/automation/, .claude/hooks/.
# ALLOW (by caller context): writes from inside a worktree (.claude/worktrees/agent-*)
#   — subagents operate there per rules/agent-protocol.md, so they may write any path.
# BLOCK: everything else (this is the orchestrator writing from the main tree).

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "minimal" || exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

is_path_allow_listed() {
    [[ -z "$1" || "$1" =~ \.md$ ]] && return 0
    [[ "$1" =~ \.claude/automation/ || "$1" =~ \.claude/hooks/ ]]
}

is_caller_in_worktree() {
    local toplevel
    toplevel=$(git rev-parse --show-toplevel 2>/dev/null)
    [[ "$toplevel" == *"/.claude/worktrees/agent-"* ]] || [[ "$PWD" == *"/.claude/worktrees/agent-"* ]]
}

if is_path_allow_listed "$FILE_PATH"; then
    exit 0
fi

if is_caller_in_worktree; then
    exit 0
fi

echo "BLOCKED: Orchestrator cannot write source files directly. Delegate to an agent via the appropriate skill." >&2
exit 2

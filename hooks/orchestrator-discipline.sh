#!/usr/bin/env bash
# Orchestrator Discipline Hook — PreToolUse hook for Write and Edit tools
#
# Blocks the orchestrator from writing source files directly.
# The orchestrator must delegate all file changes to agents via skills.
#
# ALLOW (by path): .md files, .claude/automation/, .claude/hooks/, .claude-sessions/.
# ALLOW (by caller context): tool call originates from a subagent — harness injects
#   `subagent_type` into PreToolUse stdin JSON for every subagent tool call; the
#   orchestrator's own tool calls always have an empty subagent_type.
#   CWD-based worktree detection is kept as a fallback but is unreliable because
#   hooks run with the main session's CWD, not the subagent's CWD.
# BLOCK: everything else (this is the orchestrator writing from the main tree).
#
# enforces: rules/core.md:Iron Laws
# protects: build-implementation, all-skills

_OD_HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=/dev/null
source "$_OD_HOOK_DIR/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Write}"
trap 'log_hook_event $?' EXIT

source "$_OD_HOOK_DIR/hook-profile.sh" && check_hook_profile "minimal" || exit 0
# is_protected_path: block-by-protected-location helper (consults git index)
source "$_OD_HOOK_DIR/_lib/is-protected-path.sh"

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.subagent_type // empty')

is_path_allow_listed() {
    # Empty path is a no-op target — allow.
    [[ -z "$1" ]] && return 0
    [[ "$1" =~ \.claude/automation/ || "$1" =~ \.claude/hooks/ ]] && return 0
    # pipeline-state token files (e.g. approval.token) are orchestrator-state,
    # not source code. Both regular and workstream layouts are covered by the
    # single regex: any `.token` under any `pipeline-state/` directory.
    [[ "$1" =~ /pipeline-state/.*\.token$ ]] && return 0
    # Freshness-gate evidence files are orchestrator-state, not source.
    # Allow refresh of stale stubs in-cycle per Iron Law 6 (regular +
    # workstream layouts both match via the `.*` between pipeline-state
    # and the filename). `$` anchor prevents `.json.bak` from sneaking in.
    [[ "$1" =~ /pipeline-state/.*/verification-evidence\.json$ ]] && return 0
    # Subagent worktrees: only spawned agents write here. Treat ".claude/worktrees/"
    # as implicitly trusted (ownership implied by path), same as ".claude/hooks/".
    [[ "$1" =~ /\.claude/worktrees/ ]] && return 0
    [[ "$1" =~ /\.claude-sessions/ ]] && return 0
    # For .md paths: replace the old substring allowlist (/.claude/|/memory/|/rules/|
    # /pipeline-state/) with is_protected_path which consults the git index.
    # is_protected_path exit 0 = BLOCK; exit 1 = ALLOW.
    # The old allowlist matched every file in a repo whose root IS .claude —
    # this fix blocks git-tracked files regardless of their containing directory.
    if [[ "$1" =~ \.md$ ]]; then
        ! is_protected_path "$1"
        return
    fi
    # All other non-allowlisted paths — block.
    return 1
}

is_caller_a_subagent() {
    # Primary: harness injects subagent_type for every subagent tool call.
    # Empty = orchestrator's own call. Non-empty = delegated to an agent.
    [[ -n "$SUBAGENT_TYPE" ]] && return 0
    # Fallback: CWD-based worktree check (unreliable — hook CWD is the main
    # session CWD, not the agent CWD — but kept for belt-and-suspenders).
    local toplevel
    toplevel=$(git rev-parse --show-toplevel 2>/dev/null)
    [[ "$toplevel" == *"/.claude/worktrees/agent-"* ]] || [[ "$PWD" == *"/.claude/worktrees/agent-"* ]] || [[ "$toplevel" == *"/.claude-sessions/"* ]] || [[ "$PWD" == *"/.claude-sessions/"* ]]
}

if is_path_allow_listed "$FILE_PATH"; then
    exit 0
fi

if is_caller_a_subagent; then
    exit 0
fi

echo "BLOCKED: Orchestrator cannot write source files directly. Delegate to an agent via the appropriate skill." >&2
exit 2

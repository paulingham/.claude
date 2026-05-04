#!/usr/bin/env bash
# Settings Path Lint — PreToolUse Bash hook (commit/push filter).
#
# Refuses `git commit` / `git push` when ~/.claude/settings.json contains
# hardcoded absolute home-directory paths (`/Users/<name>/.claude/...` or
# `/home/<name>/.claude/...`). The portable form is `$HOME/.claude/...`.
#
# Mirrors the worktree-trust policy of orchestrator-discipline / bash-write-guard:
#   - Calls from inside a worktree are ALLOWED (agent-managed commits).
#   - Calls from the orchestrator (PWD = main tree) are LINTED.
#
# enforces: rules/_detail/agent-protocol.md:Portable Config Dir
# protects: harness-config

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Bash}"
trap 'log_hook_event $?' EXIT

set -uo pipefail

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[[ "$TOOL_NAME" != "Bash" ]] && exit 0
[[ -z "$COMMAND" ]] && exit 0
[[ "$COMMAND" =~ git[[:space:]]+(commit|push) ]] || exit 0

is_caller_in_worktree() {
    local toplevel
    toplevel=$(git rev-parse --show-toplevel 2>/dev/null)
    [[ "$toplevel" == *"/.claude/worktrees/agent-"* ]] || [[ "$PWD" == *"/.claude/worktrees/agent-"* ]]
}

is_caller_in_worktree && exit 0

# CLAUDE_SETTINGS_FILE is a test-only override; production reads the real file.
SETTINGS_FILE="${CLAUDE_SETTINGS_FILE:-$HOME/.claude/settings.json}"
[[ -r "$SETTINGS_FILE" ]] || exit 0

OFFENDERS=$(grep -E '"(/Users/|/home/)[^/"]+/\.claude/' "$SETTINGS_FILE" 2>/dev/null || true)
[[ -z "$OFFENDERS" ]] && exit 0

cat >&2 <<EOF
BLOCKED: settings.json contains hardcoded absolute home-directory paths.
Offending lines:
$OFFENDERS

Use \$HOME/.claude/... or a 'bash -c' wrapper that expands at runtime.
The portable form survives moves between machines and users.
EOF
exit 2

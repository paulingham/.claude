#!/usr/bin/env bash
# TDD Guard — PreToolUse hook on Bash.
# Blocks `gh pr create` / `gh pr ready` when the PR diff contains source
# changes with no accompanying test changes. Exits 0 immediately for any
# non-PR-creation Bash command. Enforces ATDD discipline at the PR boundary.

source ~/.claude/hooks/_lib/log.sh
_log_hook_start
_log_hook_trigger "PreToolUse:Bash"
trap 'log_hook_event $?' EXIT

set -uo pipefail

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Filter: only fire on `gh pr create` / `gh pr ready`. All other Bash exits 0.
case "$COMMAND" in
  *"gh pr create"*|*"gh pr ready"*) ;;
  *) exit 0 ;;
esac

# Loop-guard runs only for PR commands — non-PR Bash must not consume slots.
source ~/.claude/hooks/loop-guard.sh && check_loop_guard "tdd-guard" || exit 0

LIB="$(dirname "${BASH_SOURCE[0]}")/_lib"
# shellcheck source=_lib/tdd-guard-pr.sh
source "$LIB/tdd-guard-pr.sh"
_tdd_guard_pr_run "$COMMAND"

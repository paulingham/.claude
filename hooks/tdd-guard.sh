#!/usr/bin/env bash
# TDD Guard — PreToolUse hook on Bash.
# Blocks `gh pr create` / `gh pr ready` when the PR diff contains source
# changes with no accompanying test changes. Exits 0 immediately for any
# non-PR-creation Bash command. Enforces ATDD discipline at the PR boundary.
#
# enforces: protocols/atdd-procedure.md:ATDD Anti-Patterns
# protects: build-implementation, pr-creation
# self-test: skip

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Bash"
trap 'log_hook_event $?' EXIT

set -uo pipefail

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0

command -v jq >/dev/null 2>&1 || exit 0

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Filter: only fire on `gh pr create` / `gh pr ready`. All other Bash exits 0.
case "$COMMAND" in
  *"gh pr create"*|*"gh pr ready"*) ;;
  *) exit 0 ;;
esac

# Loop-guard runs only for PR commands — non-PR Bash must not consume slots.
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/loop-guard.sh" && check_loop_guard "tdd-guard" || exit 0

LIB="$(dirname "${BASH_SOURCE[0]}")/_lib"
# shellcheck source=_lib/tdd-guard-pr.sh
source "$LIB/tdd-guard-pr.sh"

# Write pairing snapshot for SubagentStop forensics (Wave 5 / A8.2)
source "$LIB/tdd-guard-pairing.sh" 2>/dev/null
source "$LIB/jsonl-emit.sh" 2>/dev/null
TASK_ID="${CLAUDE_PIPELINE_TASK_ID:-unknown}"
[[ "$TASK_ID" != "unknown" ]] && declare -F _tdg_write_snapshot >/dev/null && _tdg_write_snapshot "$TASK_ID"

_tdd_guard_pr_run "$COMMAND"; RC=$?
if [[ "$RC" -eq 0 && "$TASK_ID" != "unknown" ]] && declare -F _tdg_events_path >/dev/null && declare -F _jsonl_emit >/dev/null; then
  EVENTS=$(_tdg_events_path); mkdir -p "$(dirname "$EVENTS")"
  _jsonl_emit "$EVENTS" source passed task_id "$TASK_ID"
fi
exit "$RC"

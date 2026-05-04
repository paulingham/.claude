#!/usr/bin/env bash
# Quality Gate Hook — PreToolUse on "gh pr create"
# Refactored: per-check logic extracted to _lib/quality-gate-checks.sh
# (instinct: file >44 lines requires _lib/ extraction before adding new logic)
#
# enforces: rules/_detail/pipeline-protocol.md:Phase Checklist
# protects: pr-creation, code-review
# self-test: skip

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Bash"
trap 'log_hook_event $?' EXIT

set -uo pipefail

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh" && check_hook_profile "minimal" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
[[ "$TOOL_NAME" != "Bash" || ! "$COMMAND" =~ "gh pr create" ]] && exit 0

echo "QUALITY GATE: Running pre-PR checks..." >&2
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/quality-gate-checks.sh"
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/quality-gate-pairing.sh"
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/jsonl-emit.sh"

RT=$(_qg_detect_runtime)
ANY_FAILED=0
for check in tests lint audit shape contract; do
  _qg_check_${check} "$RT"
  rc=$?
  [[ $rc -ne 0 ]] && ANY_FAILED=1
done

TASK_ID="${CLAUDE_PIPELINE_TASK_ID:-unknown}"
EVENTS=$(_qg_events_path)
mkdir -p "$(dirname "$EVENTS")"
if [[ $ANY_FAILED -eq 0 ]]; then
  _qg_write_snapshot "$TASK_ID"
  _jsonl_emit "$EVENTS" source passed task_id "$TASK_ID"
  echo "QUALITY GATE PASSED" >&2
  exit 0
else
  _jsonl_emit "$EVENTS" source prevented task_id "$TASK_ID"
  echo "QUALITY GATE FAILED: Fix issues before creating PR" >&2
  exit 2
fi

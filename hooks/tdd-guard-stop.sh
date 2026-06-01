#!/usr/bin/env bash
# SubagentStop forensic re-check for tdd-guard invariant
# enforces: protocols/atdd-procedure.md:ATDD Anti-Patterns
# protects: build-implementation, pr-creation

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SubagentStop"
trap 'log_hook_event $?' EXIT

set -uo pipefail

INPUT=$(cat 2>/dev/null) || INPUT=""
[ "$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ] && exit 0

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/tdd-guard-pairing.sh" 2>/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/jsonl-emit.sh" 2>/dev/null

TASK_ID="${CLAUDE_PIPELINE_TASK_ID:-}"
TASK_ID="${TASK_ID//[^a-zA-Z0-9_.-]/}"
[[ -z "$TASK_ID" ]] && exit 0

EVENTS=$(_tdg_events_path)
[[ -f "$EVENTS" ]] || exit 0

CURSOR=$(_tdg_read_cursor "$TASK_ID")
TOTAL=$(wc -l < "$EVENTS" | tr -d ' ')
[[ "$TOTAL" -le "$CURSOR" ]] && exit 0

METRICS="$HARNESS_DATA/metrics/${CLAUDE_SESSION_ID:-local}/tdd-guard-violations.jsonl"
mkdir -p "$(dirname "$METRICS")"

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  SOURCE=$(echo "$line" | jq -r '.source // empty' 2>/dev/null)
  if [[ "$SOURCE" == "passed" ]]; then
    SNAP=$(_tdg_snapshot_path "$TASK_ID")
    PREV_FILES=$(jq -r '.diff_files // 0' "$SNAP" 2>/dev/null || echo "0")
    CURR_FILES=$(git diff HEAD~1 HEAD --name-only 2>/dev/null | wc -l | tr -d ' ')
    [[ "$CURR_FILES" -lt "$PREV_FILES" ]] && RESULT="drift-detected" || RESULT="post-confirmed"
    _jsonl_emit "$METRICS" source "$RESULT" task_id "$TASK_ID" hook tdd-guard-stop
  fi
done < <(tail -n +"$((CURSOR+1))" "$EVENTS")

_tdg_write_cursor "$TASK_ID" "$TOTAL"
exit 0

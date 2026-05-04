#!/usr/bin/env bash
# SubagentStop forensic re-check for tdd-guard invariant
# enforces: rules/_detail/atdd-procedure.md:ATDD Anti-Patterns
# protects: build-implementation, pr-creation

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SubagentStop"
trap 'log_hook_event $?' EXIT

set -uo pipefail

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0
source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/tdd-guard-pairing.sh" 2>/dev/null

TASK_ID="${CLAUDE_PIPELINE_TASK_ID:-}"
[[ -z "$TASK_ID" ]] && exit 0

EVENTS=$(_tdg_events_path)
[[ -f "$EVENTS" ]] || exit 0

CURSOR=$(_tdg_read_cursor "$TASK_ID")
TOTAL=$(wc -l < "$EVENTS" | tr -d ' ')
[[ "$TOTAL" -le "$CURSOR" ]] && exit 0

METRICS="${HOME}/.claude/metrics/${CLAUDE_SESSION_ID:-local}/tdd-guard-violations.jsonl"
mkdir -p "$(dirname "$METRICS")"

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  SOURCE=$(echo "$line" | jq -r '.source // empty' 2>/dev/null)
  if [[ "$SOURCE" == "passed" ]]; then
    SNAP=$(_tdg_snapshot_path "$TASK_ID")
    PREV_FILES=$(jq -r '.diff_files // 0' "$SNAP" 2>/dev/null || echo "0")
    CURR_FILES=$(git diff HEAD~1 HEAD --name-only 2>/dev/null | wc -l | tr -d ' ')
    [[ "$CURR_FILES" -lt "$PREV_FILES" ]] && RESULT="drift-detected" || RESULT="post-confirmed"
    python3 -c "import json,time; print(json.dumps({'source':'$RESULT','task_id':'$TASK_ID','ts':int(time.time()),'hook':'tdd-guard-stop'}))" >> "$METRICS"
  fi
done < <(tail -n +"$((CURSOR+1))" "$EVENTS")

_tdg_write_cursor "$TASK_ID" "$TOTAL"
exit 0

#!/usr/bin/env bash
# SubagentStop forensic re-check for quality-gate invariant
# enforces: protocols/pipeline-protocol.md:Phase Checklist
# protects: pr-creation, code-review

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
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/quality-gate-checks.sh" 2>/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/quality-gate-pairing.sh" 2>/dev/null
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/jsonl-emit.sh" 2>/dev/null

TASK_ID="${CLAUDE_PIPELINE_TASK_ID:-}"
if [[ -z "$TASK_ID" ]]; then
  TASK_ID=$(grep -rh "^task_id:" "$HARNESS_DATA/pipeline-state" 2>/dev/null | head -1 | awk '{print $2}')
fi
TASK_ID="${TASK_ID//[^a-zA-Z0-9_.-]/}"
[[ -z "$TASK_ID" ]] && exit 0

EVENTS=$(_qg_events_path)
[[ -f "$EVENTS" ]] || exit 0

CURSOR=$(_qg_read_cursor "$TASK_ID")
TOTAL=$(wc -l < "$EVENTS" | tr -d ' ')
[[ "$TOTAL" -le "$CURSOR" ]] && exit 0

METRICS="$HARNESS_DATA/metrics/${CLAUDE_SESSION_ID:-local}/quality-gate-violations.jsonl"
mkdir -p "$(dirname "$METRICS")"

while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  SOURCE=$(echo "$line" | jq -r '.source // empty' 2>/dev/null)
  if [[ "$SOURCE" == "passed" ]]; then
    RT=$(_qg_detect_runtime)
    _qg_check_tests "$RT" >/dev/null 2>&1 && RESULT="post-confirmed" || RESULT="drift-detected"
    _jsonl_emit "$METRICS" source "$RESULT" task_id "$TASK_ID" hook quality-gate-stop
  fi
done < <(tail -n +"$((CURSOR+1))" "$EVENTS")

_qg_write_cursor "$TASK_ID" "$TOTAL"
exit 0

#!/usr/bin/env bash
# mutation-score-gate.sh — SubagentStop advisory-log hook (exit 0 ALWAYS).
# Records mutation-score signal for changed lines after software-engineer /
# fix-engineer subagents complete. Writes to:
#   $HARNESS_DATA/metrics/$SESSION_ID/mutation-score.jsonl
#
# ADVISORY-LOG mode: exit 0 always. No exit 2 path exists anywhere in this
# script. Purpose: gather soak data so the N-SESSION PROMOTION CRITERION can
# be evaluated before considering a flip to enforcing.
#
# N-SESSION PROMOTION CRITERION:
#   >=10 distinct sessions with median changed-line mutation score >=70%
#   AND zero false-blocks observed before considering a flip to enforcing
#   (exit 2). Until that criterion is met: advisory-log only.
#   if-broken-look-at: $HARNESS_DATA/metrics/*/mutation-score.jsonl
#                      skills/mutation-score-report/SKILL.md
#
# enforces: rules/core.md Iron Law 1 (ASPIRATIONAL — soak phase)
# protects: pipeline (advisory telemetry only)
set -uo pipefail

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SubagentStop"
trap 'log_hook_event $?' EXIT

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/hook-profile.sh" 2>/dev/null && check_hook_profile "standard" || exit 0

# Roles that produce changed-lines mutation signal worth recording.
readonly ALLOWED_ROLES="software-engineer fix-engineer"

# sanitize_id: strip unsafe chars; return 'unknown' on empty / traversal.
# Only [A-Za-z0-9._-] is safe for use in a filesystem path segment.
sanitize_id() {
  local raw="$1"
  if [[ "$raw" =~ ^[A-Za-z0-9._-]+$ ]]; then
    printf '%s' "$raw"
  else
    printf 'unknown'
  fi
}

# read_stdin_safe: capture stdin; exit 0 on read failure.
read_stdin_safe() {
  INPUT=$(cat 2>/dev/null) || { exit 0; }
  printf '%s' "$INPUT"
}

# parse_stop_active: returns "true" when this is a nested SubagentStop.
parse_stop_active() {
  local raw_input="$1"
  echo "$raw_input" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false"
}

# parse_agent_role: extract role from stdin JSON; empty string on failure.
parse_agent_role() {
  local raw_input="$1"
  echo "$raw_input" \
    | jq -r '.subagent_type // .agent_type // empty' 2>/dev/null || true
}

# parse_session_id: extract session_id from stdin JSON; 'unknown' on failure.
parse_session_id() {
  local raw_input="$1"
  echo "$raw_input" | jq -r '.session_id // "unknown"' 2>/dev/null || echo "unknown"
}

# parse_task_id: extract task_id from stdin JSON; 'unknown' on failure.
parse_task_id() {
  local raw_input="$1"
  echo "$raw_input" | jq -r '.task_id // "unknown"' 2>/dev/null || echo "unknown"
}

# parse_changed_files_count: count changed_files array entries.
parse_changed_files_count() {
  local raw_input="$1"
  echo "$raw_input" \
    | jq -r '(.changed_files // []) | length' 2>/dev/null || echo "0"
}

# role_is_allowed: returns 0 when role is in ALLOWED_ROLES, 1 otherwise.
role_is_allowed() {
  local role="$1"
  [[ -z "$role" ]] && return 1
  local r
  for r in $ALLOWED_ROLES; do
    [[ "$role" == "$r" ]] && return 0
  done
  return 1
}

# tool_available: returns true/false string for whether a mutation tool exists.
mutation_tool_available() {
  if command -v mutmut > /dev/null 2>&1; then
    printf 'true'
  elif command -v stryker > /dev/null 2>&1; then
    printf 'true'
  else
    printf 'false'
  fi
}

# ensure_metrics_dir: create metrics dir for session; exit 0 on failure.
ensure_metrics_dir() {
  local dir="$1"
  mkdir -p "$dir" 2>/dev/null || exit 0
}

# write_jsonl_record: append one JSONL record to the target file.
write_jsonl_record() {
  local jsonl_path="$1" session_id="$2" task_id="$3"
  local agent_role="$4" changed_count="$5" tool_avail="$6"
  local ts
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "unknown")
  jq -c -n \
    --arg ts "$ts" \
    --arg sid "$session_id" \
    --arg tid "$task_id" \
    --arg role "$agent_role" \
    --argjson count "$changed_count" \
    --arg tool "$tool_avail" \
    '{timestamp: $ts, session_id: $sid, task_id: $tid,
      agent_role: $role, changed_files_count: $count,
      mutation_score: null, tool_available: ($tool == "true"),
      note: "advisory-log: real score pending tool availability"}' \
    >> "$jsonl_path" 2>/dev/null || true
}

# --- main ---

INPUT=$(read_stdin_safe)

# Fail-open on empty / unparseable stdin.
if [[ -z "$INPUT" ]]; then exit 0; fi

STOP_ACTIVE=$(parse_stop_active "$INPUT")
# Nested SubagentStop: neutralise EXIT-trap logger, no-op.
[[ "$STOP_ACTIVE" == "true" ]] && { trap - EXIT; exit 0; }

AGENT_ROLE=$(parse_agent_role "$INPUT")

# Early-exit when role is not in the signal-producing set.
role_is_allowed "$AGENT_ROLE" || exit 0

SESSION_ID=$(sanitize_id "$(parse_session_id "$INPUT")")
TASK_ID=$(sanitize_id "$(parse_task_id "$INPUT")")
CHANGED_COUNT=$(parse_changed_files_count "$INPUT")
TOOL_AVAIL=$(mutation_tool_available)

METRICS_DIR="${HARNESS_DATA}/metrics/${SESSION_ID}"
ensure_metrics_dir "$METRICS_DIR"

JSONL_PATH="${METRICS_DIR}/mutation-score.jsonl"
write_jsonl_record \
  "$JSONL_PATH" "$SESSION_ID" "$TASK_ID" \
  "$AGENT_ROLE" "$CHANGED_COUNT" "$TOOL_AVAIL"

exit 0

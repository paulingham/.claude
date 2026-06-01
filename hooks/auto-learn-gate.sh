#!/usr/bin/env bash
# Auto-Learn Gate — Stop hook. Fires a context message telling the orchestrator
# to invoke /learn when thresholds are met. Never invokes /learn directly.
# Test override: CLAUDE_LEARN_TEST_HASH sets the learning/<hash> dir explicitly.
#
# enforces: protocols/autonomous-intelligence.md:Consolidation Gate
# protects: learn

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "Stop"
trap 'log_hook_event $?' EXIT    # set BEFORE any early exits so they get logged

[[ "${CLAUDE_DISABLE_AUTO_LEARN:-0}" == "1" ]] && exit 0
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "standard" || exit 0

LIB="$(dirname "${BASH_SOURCE[0]}")/_lib"
# shellcheck source=_lib/project-hash.sh
source "$LIB/project-hash.sh"
# shellcheck source=_lib/auto-learn-state.sh
source "$LIB/auto-learn-state.sh"
# shellcheck source=_lib/auto-learn-lock.sh
source "$LIB/auto-learn-lock.sh"
# shellcheck source=_lib/auto-learn-gate-core.sh
source "$LIB/auto-learn-gate-core.sh"
# shellcheck source=_lib/learning-flock.sh
source "$LIB/learning-flock.sh"

INPUT=$(cat)  # capture Stop event JSON
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
[ "$STOP_HOOK_ACTIVE" = "true" ] && exit 0
HASH="${CLAUDE_LEARN_TEST_HASH:-$(_project_hash --fallback "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")")}"
LD="$HARNESS_DATA/learning/$HASH"
STATE="$LD/.learn-state.json"; OBS="$LD/observations.jsonl"; LOG="$LD/.learn-gate.log"; LOCK="$LD/.learn-state.lock"
mkdir -p "$LD"

if [[ ! -d "$LD/instincts" ]]; then
  printf '[auto-learn-gate] WARN instincts/ missing — bootstrap (fix #1) did not complete for project-hash=%s\n' "$HASH" >&2
  exit 0
fi

# Outer flock coordinates with learning-gc.sh; inner mkdir lock guards the
# state file against re-entrant Stop firings within the same hook process.
_alg_inner() {
  local S OFF LAST_FIRED LAST_RUN LAST_STARTED PIPES OBS_COUNT NEW_IDS NEW_N NEW_SIZE LATEST_PID CUR_PID OUT
  S=$(_als_read_state "$STATE")
  OFF=$(echo "$S" | jq -r '.last_observation_offset // 0')
  LAST_FIRED=$(echo "$S" | jq -r '.last_fired_pipeline_id // ""')
  LAST_RUN=$(echo "$S" | jq -r '.last_learn_run')
  LAST_STARTED=$(echo "$S" | jq -r '.last_learn_started // ""')
  PIPES=$(echo "$S" | jq -r '.pipelines_since_learn // 0')
  OBS_COUNT=$(echo "$S" | jq -r '.observations_since_learn // 0')
  NEW_IDS=$(_als_count_pipeline_records "$OBS" "$OFF")
  NEW_N=$(printf '%s\n' "$NEW_IDS" | grep -c . 2>/dev/null || echo 0)
  NEW_SIZE=$(_als_file_size "$OBS")
  LATEST_PID=$(_als_latest_pipeline_id "$OBS" "$OFF")
  CUR_PID=$(_alg_current_pipeline_id); [[ -z "$CUR_PID" ]] && CUR_PID="$LATEST_PID"
  OBS_COUNT=$(( OBS_COUNT + NEW_N ))
  if [[ "$NEW_N" -gt 0 && -n "$LATEST_PID" && "$LATEST_PID" != "$LAST_FIRED" ]]; then
    PIPES=$(( PIPES + 1 ))
  fi
  if _alg_should_fire "$OBS_COUNT" "$PIPES" "$LAST_RUN" "$CUR_PID" "$LAST_FIRED"; then
    _alg_print_trigger "$OBS_COUNT" "$PIPES"
    LAST_FIRED="${CUR_PID:-$LAST_FIRED}"
  else
    [[ -f "$LOG" && $(_als_file_size "$LOG") -gt 1048576 ]] && mv "$LOG" "$LOG.1"
    printf '[auto-learn-gate] obs=%s pipelines=%s last_run=%s gate=not-met\n' "$OBS_COUNT" "$PIPES" "$LAST_RUN" >> "$LOG"
  fi
  OUT=$(jq -n --arg lr "$LAST_RUN" --arg ls "$LAST_STARTED" --argjson p "$PIPES" --argjson o "$OBS_COUNT" --arg fp "$LAST_FIRED" --argjson off "$NEW_SIZE" \
    '{last_learn_run:(if $lr=="null" then null else $lr end),last_learn_started:(if $ls=="" then null else $ls end),pipelines_since_learn:$p,observations_since_learn:$o,last_fired_pipeline_id:(if $fp=="" then null else $fp end),last_observation_offset:$off}')
  _als_write_state "$STATE" "$OUT"
}

_alg_run_locked() {
  _all_acquire "$LOCK" 25 || return 0
  trap '_all_release "$LOCK"; log_hook_event $?' EXIT
  _alg_inner
}

with_learning_lock "$HASH" -- _alg_run_locked
exit 0

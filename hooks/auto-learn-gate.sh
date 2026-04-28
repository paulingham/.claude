#!/usr/bin/env bash
# Auto-Learn Gate — Stop hook. Fires a context message telling the orchestrator
# to invoke /learn when thresholds are met. Never invokes /learn directly.
# Test override: CLAUDE_LEARN_TEST_HASH sets the learning/<hash> dir explicitly.

source ~/.claude/hooks/_lib/log.sh
_log_hook_start
_log_hook_trigger "Stop"

[[ "${CLAUDE_DISABLE_AUTO_LEARN:-0}" == "1" ]] && exit 0
source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

LIB="$(dirname "${BASH_SOURCE[0]}")/_lib"
# shellcheck source=_lib/project-hash.sh
source "$LIB/project-hash.sh"
# shellcheck source=_lib/auto-learn-state.sh
source "$LIB/auto-learn-state.sh"
# shellcheck source=_lib/auto-learn-lock.sh
source "$LIB/auto-learn-lock.sh"
# shellcheck source=_lib/auto-learn-gate-core.sh
source "$LIB/auto-learn-gate-core.sh"

cat > /dev/null  # drain stdin (Stop event JSON)
HASH="${CLAUDE_LEARN_TEST_HASH:-$(_project_hash --fallback "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")")}"
LD="$HOME/.claude/learning/$HASH"
STATE="$LD/.learn-state.json"; OBS="$LD/observations.jsonl"; LOG="$LD/.learn-gate.log"; LOCK="$LD/.learn-state.lock"
mkdir -p "$LD"

if [[ ! -d "$LD/instincts" ]]; then
  printf '[auto-learn-gate] WARN instincts/ missing — bootstrap (fix #1) did not complete for project-hash=%s\n' "$HASH" >&2
  exit 0
fi

_all_acquire "$LOCK" 25 || exit 0
trap '_all_release "$LOCK"; log_hook_event $?' EXIT

S=$(_als_read_state "$STATE")
OFF=$(echo "$S" | jq -r '.last_observation_offset // 0')
LAST_FIRED=$(echo "$S" | jq -r '.last_fired_pipeline_id // ""')
LAST_RUN=$(echo "$S" | jq -r '.last_learn_run')
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

OUT=$(jq -n --arg lr "$LAST_RUN" --argjson p "$PIPES" --argjson o "$OBS_COUNT" --arg fp "$LAST_FIRED" --argjson off "$NEW_SIZE" \
  '{last_learn_run:(if $lr=="null" then null else $lr end),pipelines_since_learn:$p,observations_since_learn:$o,last_fired_pipeline_id:(if $fp=="" then null else $fp end),last_observation_offset:$off}')
_als_write_state "$STATE" "$OUT"
exit 0

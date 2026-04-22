#!/bin/bash
# Cost Tracker — Stop hook
# Appends session metrics to ~/.claude/metrics/costs.jsonl
# Passive logging only (exit 0).

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

INPUT=$(cat)

# Avoid loops
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    exit 0
fi

METRICS_DIR="$HOME/.claude/metrics"
mkdir -p "$METRICS_DIR"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
PROJECT=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
# shellcheck source=_lib/project-hash.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib/project-hash.sh"
# shellcheck source=_lib/state-dir.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib/state-dir.sh"
PROJECT_HASH=$(_project_hash --fallback "")

# Session ID: read from state file (created by observation-capture)
SESSION_FILE=$(_state_path "session-${PPID}")
if [[ -f "$SESSION_FILE" ]]; then
    SESSION_ID=$(cat "$SESSION_FILE")
else
    SESSION_ID=""
fi

# Duration: calculate from session start time file
START_TIME_FILE=$(_state_path "session-start-${PPID}")
if [[ -f "$START_TIME_FILE" ]]; then
    START_EPOCH=$(cat "$START_TIME_FILE")
    NOW_EPOCH=$(date +%s)
    DURATION_S=$(( NOW_EPOCH - START_EPOCH ))
else
    DURATION_S=0
fi

# Tool calls: count observations written during this session
TOOL_CALLS=0
if [[ -n "$SESSION_ID" ]]; then
    LEARNING_DIR="$HOME/.claude/learning/$PROJECT_HASH"
    OBS_FILE="$LEARNING_DIR/observations.jsonl"
    if [[ -f "$OBS_FILE" ]]; then
        TOOL_CALLS=$(grep -c "\"session_id\":\"$SESSION_ID\"" "$OBS_FILE" 2>/dev/null)
        TOOL_CALLS="${TOOL_CALLS:-0}"
    fi
fi

# Build enriched metrics record
jq -c -n \
    --arg ts "$TIMESTAMP" \
    --arg sid "$SESSION_ID" \
    --arg project "$PROJECT" \
    --arg hash "$PROJECT_HASH" \
    --argjson duration "$DURATION_S" \
    --argjson tools "$TOOL_CALLS" \
    '{
        "timestamp": $ts,
        "session_id": $sid,
        "project": $project,
        "project_hash": $hash,
        "event": "session_end",
        "duration_s": $duration,
        "tool_calls": $tools
    }' >> "$METRICS_DIR/costs.jsonl" 2>/dev/null || true

exit 0

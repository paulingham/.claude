#!/bin/bash
# Observation Capture — PostToolUse hook (all tools)
# Captures tool usage observations for the continuous learning system.
# Appends to ~/.claude/learning/{project-hash}/observations.jsonl
# Passive (exit 0).

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Skip internal hooks and meta tools
case "$TOOL_NAME" in
    "") exit 0 ;;
esac

# Get project hash from git remote (used for LEARNING_DIR path — backward compatible)
PROJECT_HASH=$(git remote get-url origin 2>/dev/null | md5 -q 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

# Get human-readable project name
PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

LEARNING_DIR="$HOME/.claude/learning/$PROJECT_HASH"
mkdir -p "$LEARNING_DIR"

OBS_FILE="$LEARNING_DIR/observations.jsonl"

# Rotate if >10MB
if [[ -f "$OBS_FILE" ]]; then
    SIZE=$(wc -c < "$OBS_FILE" | tr -d ' ')
    if [[ "$SIZE" -gt 10485760 ]]; then
        mv "$OBS_FILE" "${OBS_FILE}.1"
    fi
fi

# Session ID: prefer env var, fall back to temp file per parent process
SESSION_FILE="/tmp/claude-session-${PPID}"
if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
    SESSION_ID="$CLAUDE_SESSION_ID"
elif [[ -f "$SESSION_FILE" ]]; then
    SESSION_ID=$(cat "$SESSION_FILE")
else
    SESSION_ID=$(uuidgen 2>/dev/null || echo "sess-${RANDOM}-${RANDOM}")
    echo "$SESSION_ID" > "$SESSION_FILE"
fi

# Session start time: create on first invocation per session
START_TIME_FILE="/tmp/claude-session-start-${PPID}"
if [[ ! -f "$START_TIME_FILE" ]]; then
    date +%s > "$START_TIME_FILE"
fi

# Pipeline phase and agent role from env vars
PHASE="${CLAUDE_PIPELINE_PHASE:-}"
AGENT_ROLE="${CLAUDE_AGENT_ROLE:-}"

# Outcome: check tool_output for error indicators
IS_ERROR=$(echo "$INPUT" | jq -r '.tool_output.is_error // empty' 2>/dev/null)
HAS_ERROR=$(echo "$INPUT" | jq -r '.tool_output.error // empty' 2>/dev/null)
if [[ "$IS_ERROR" == "true" ]] || [[ -n "$HAS_ERROR" && "$HAS_ERROR" != "null" && "$HAS_ERROR" != "false" ]]; then
    OUTCOME="error"
else
    OUTCOME="success"
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

jq -c -n \
    --arg ts "$TIMESTAMP" \
    --arg sid "$SESSION_ID" \
    --arg tool "$TOOL_NAME" \
    --arg file "${FILE_PATH:-}" \
    --arg project "$PROJECT_NAME" \
    --arg hash "$PROJECT_HASH" \
    --arg phase "$PHASE" \
    --arg role "$AGENT_ROLE" \
    --arg outcome "$OUTCOME" \
    '{
        "timestamp": $ts,
        "session_id": $sid,
        "tool": $tool,
        "file": $file,
        "project": $project,
        "project_hash": $hash,
        "phase": $phase,
        "agent_role": $role,
        "outcome": $outcome
    }' >> "$OBS_FILE" 2>/dev/null || true

exit 0

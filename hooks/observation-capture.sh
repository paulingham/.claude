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
# shellcheck source=_lib/project-hash.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib/project-hash.sh"
# shellcheck source=_lib/state-dir.sh
source "$(dirname "${BASH_SOURCE[0]}")/_lib/state-dir.sh"
_ensure_state_dir
PROJECT_HASH=$(_project_hash --fallback "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")")

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

# Session ID: prefer env var, fall back to state file per parent process
SESSION_FILE=$(_state_path "session-${PPID}")
if [[ -n "${CLAUDE_SESSION_ID:-}" ]]; then
    SESSION_ID="$CLAUDE_SESSION_ID"
elif [[ -f "$SESSION_FILE" ]]; then
    SESSION_ID=$(cat "$SESSION_FILE")
else
    SESSION_ID=$(uuidgen 2>/dev/null || echo "sess-${RANDOM}-${RANDOM}")
    printf '%s\n' "$SESSION_ID" | _state_write "session-${PPID}"
fi

# Session start time: create on first invocation per session
START_TIME_FILE=$(_state_path "session-start-${PPID}")
if [[ ! -f "$START_TIME_FILE" ]]; then
    date +%s | _state_write "session-start-${PPID}"
fi

# Pipeline phase: from env var, or detect from active pipeline state file
PHASE="${CLAUDE_PIPELINE_PHASE:-}"
if [[ -z "$PHASE" ]]; then
    PIPELINE_DIR="$HOME/.claude/pipeline-state"
    if [[ -d "$PIPELINE_DIR" ]]; then
        # Find the active pipeline and extract current phase
        ACTIVE_FILE=$(grep -rl "in_progress" "$PIPELINE_DIR"/*-pipeline.md 2>/dev/null | head -1)
        if [[ -n "$ACTIVE_FILE" ]]; then
            # Extract the phase that's in_progress from the Phases section
            PHASE=$(grep -E "in_progress" "$ACTIVE_FILE" 2>/dev/null | head -1 | sed 's/^- //' | sed 's/:.*//' | tr -d ' ' | tr '[:upper:]' '[:lower:]')
        fi
    fi
fi

# Agent role: from env var, or from state file written by subagent-context.sh
AGENT_ROLE="${CLAUDE_AGENT_ROLE:-}"
if [[ -z "$AGENT_ROLE" ]]; then
    AGENT_ROLE_FILE=$(_state_path "agent-role-${PPID}")
    if [[ -f "$AGENT_ROLE_FILE" ]]; then
        AGENT_ROLE=$(cat "$AGENT_ROLE_FILE" 2>/dev/null || true)
    fi
fi

# Outcome: check tool_output for error indicators
IS_ERROR=$(echo "$INPUT" | jq -r '.tool_output.is_error // empty' 2>/dev/null)
HAS_ERROR=$(echo "$INPUT" | jq -r '.tool_output.error // empty' 2>/dev/null)
if [[ "$IS_ERROR" == "true" ]] || [[ -n "$HAS_ERROR" && "$HAS_ERROR" != "null" && "$HAS_ERROR" != "false" ]]; then
    OUTCOME="error"
else
    OUTCOME="success"
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

OBS_JSON=$(jq -c -n \
    --arg ts "$TIMESTAMP" \
    --arg sid "$SESSION_ID" \
    --arg tool "$TOOL_NAME" \
    --arg file "${FILE_PATH:-}" \
    --arg project "$PROJECT_NAME" \
    --arg hash "$PROJECT_HASH" \
    --arg phase "$PHASE" \
    --arg role "$AGENT_ROLE" \
    --arg outcome "$OUTCOME" \
    --arg rtype "tool_use" \
    '{
        "record_type": $rtype,
        "timestamp": $ts,
        "session_id": $sid,
        "tool": $tool,
        "file": $file,
        "project": $project,
        "project_hash": $hash,
        "phase": $phase,
        "agent_role": $role,
        "outcome": $outcome
    }' 2>/dev/null) || OBS_JSON=""

if [[ -n "$OBS_JSON" ]]; then
    printf '%s\n' "$OBS_JSON" >> "$OBS_FILE" 2>/dev/null || true

    # Best-effort SQLite live write (Story 2). JSONL is canonical — any failure
    # here MUST NOT affect hook exit code or the JSONL append above.
    LIVE_DB="$HOME/.claude/db/memory.sqlite"
    LIVE_LOG="$HOME/.claude/db/live-writer.log"
    if [[ -f "$LIVE_DB" ]]; then
        # Rotate log if >1MB
        if [[ -f "$LIVE_LOG" ]] && [[ $(wc -c < "$LIVE_LOG" | tr -d ' ') -gt 1048576 ]]; then
            mv "$LIVE_LOG" "${LIVE_LOG}.1"
        fi
        printf '%s' "$OBS_JSON" | \
            PYTHONPATH="$HOME/.claude/skills/reindex-memory" \
            python3 "$HOME/.claude/skills/reindex-memory/_lib/live_writer.py" \
            2>>"$LIVE_LOG" || true
    fi
fi

exit 0

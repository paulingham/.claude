#!/bin/bash
# Observation Capture — PostToolUse hook (all tools)
# Captures tool usage observations for the continuous learning system.
# Appends to ~/.claude/learning/{project-hash}/observations.jsonl
# Passive (exit 0).

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
FILE_PATH="${CLAUDE_FILE_PATH:-}"

# Skip internal hooks and meta tools
case "$TOOL_NAME" in
    "") exit 0 ;;
esac

# Get project hash from git remote or cwd
PROJECT_ID=$(git remote get-url origin 2>/dev/null | md5 -q 2>/dev/null || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")

LEARNING_DIR="$HOME/.claude/learning/$PROJECT_ID"
mkdir -p "$LEARNING_DIR"

OBS_FILE="$LEARNING_DIR/observations.jsonl"

# Rotate if >10MB
if [[ -f "$OBS_FILE" ]]; then
    SIZE=$(wc -c < "$OBS_FILE" | tr -d ' ')
    if [[ "$SIZE" -gt 10485760 ]]; then
        mv "$OBS_FILE" "${OBS_FILE}.1"
    fi
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

jq -n \
    --arg ts "$TIMESTAMP" \
    --arg tool "$TOOL_NAME" \
    --arg file "${FILE_PATH:-}" \
    '{"timestamp":$ts,"tool":$tool,"file":$file}' \
    >> "$OBS_FILE" 2>/dev/null || true

exit 0

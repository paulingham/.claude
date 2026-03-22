#!/usr/bin/env bash
# Trajectory recorder — SubagentStop hook
# Appends a structured record to the active pipeline trajectory file when an agent stops.
# Activate by setting CLAUDE_PIPELINE_TASK_ID in your environment or pipeline start.

set -uo pipefail

INPUT=$(cat)
AGENT_TYPE=$(echo "$INPUT" | jq -r '.subagent_type // .agent_type // "unknown"' 2>/dev/null || echo "unknown")
TASK_ID="${CLAUDE_PIPELINE_TASK_ID:-}"

if [[ -z "$TASK_ID" ]]; then
  exit 0  # No active pipeline — skip
fi

# Sanitize TASK_ID to prevent path traversal
TASK_ID="${TASK_ID//[^a-zA-Z0-9_.-]/}"

TRAJECTORY_FILE="${HOME}/.claude/pipeline-state/${TASK_ID}-trajectory.jsonl"

# Guard against path traversal — file must be under pipeline-state/
case "$TRAJECTORY_FILE" in
  "${HOME}/.claude/pipeline-state/"*) ;;
  *) exit 0 ;;
esac

if [[ ! -d "${HOME}/.claude/pipeline-state" ]]; then
  exit 0
fi

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

jq -n \
  --arg ts "$TIMESTAMP" \
  --arg agent "$AGENT_TYPE" \
  --arg task_id "$TASK_ID" \
  '{"timestamp":$ts,"agent":$agent,"event":"agent_stopped","task_id":$task_id}' \
  >> "$TRAJECTORY_FILE" 2>/dev/null || true

exit 0

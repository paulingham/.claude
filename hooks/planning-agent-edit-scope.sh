#!/usr/bin/env bash
# PreToolUse hook: scope-guards the planning-agent's Edit access.
# Allows only edits to pipeline-state/<id>-plan.md files.
# Other paths: exit 2 (blocked) and logged.
set -uo pipefail

TOOL_NAME="${CLAUDE_TOOL_NAME:-}"
SUBAGENT_TYPE="${CLAUDE_SUBAGENT_TYPE:-}"
FILE_PATH="${CLAUDE_TOOL_INPUT_FILE_PATH:-}"

[[ "$SUBAGENT_TYPE" != "planning-agent" ]] && exit 0
case "$TOOL_NAME" in
  Edit|Write|MultiEdit) ;;
  *) exit 0 ;;
esac

if [[ "$FILE_PATH" =~ pipeline-state/[^/]+-plan\.md$ ]]; then
  exit 0
fi

SESSION="${CLAUDE_SESSION_ID:-unknown}"
LOG_DIR="${HOME:-/tmp}/.claude/metrics/$SESSION"
mkdir -p "$LOG_DIR"
TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '{"ts":"%s","subagent_type":"planning-agent","tool":"%s","attempted_path":"%s","action":"blocked"}\n' \
  "$TS" "$TOOL_NAME" "$FILE_PATH" >> "$LOG_DIR/planning-agent-scope-violations.jsonl"

echo "BLOCKED: planning-agent may only Edit pipeline-state/*-plan.md files. Attempted: $FILE_PATH" >&2
exit 2

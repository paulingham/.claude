#!/usr/bin/env bash
# Tool-timing capture — PostToolUse + PostToolUseFailure hook.
# Writes one JSONL line per tool call to metrics/{session}/tool-timings.jsonl.
# Fields: ts, tool, duration_ms, success, agent_role, task_id (in that order).
# success = false when invoked from PostToolUseFailure (boolean is the contract;
# future int consumers carry the cast). Missing agent_role / task_id are
# OMITTED, never written as JSON null. JSON emission goes through Python
# json.dumps in hooks/_lib/tool-timing-emit.py — never bash printf.
#
# enforces: protocols/agent-protocol.md:Resource Bounds
# protects: pipeline, forensics

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PostToolUse"
trap 'log_hook_event $?' EXIT

INPUT=$(cat)
EVENT=$(printf '%s' "$INPUT" | jq -r '.hook_event_name // "PostToolUse"' 2>/dev/null)
[[ "$EVENT" == "PostToolUseFailure" ]] && _log_hook_trigger "PostToolUseFailure"

DURATION=$(printf '%s' "$INPUT" | jq -r '.duration_ms // empty' 2>/dev/null)
[[ -z "$DURATION" ]] && exit 0

TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // ""' 2>/dev/null)
ROLE=$(printf '%s' "$INPUT" | jq -r '.tool_input.subagent_type // ""' 2>/dev/null)
TASK="${CLAUDE_PIPELINE_TASK_ID:-}"
[[ "$EVENT" == "PostToolUseFailure" ]] && SUCCESS="false" || SUCCESS="true"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

SID_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SID="${SID_RAW//[^A-Za-z0-9_-]/}"
[[ -z "$SID" ]] && SID="local-$$"
DIR="${CLAUDE_HOOK_LOG_DIR:-$HOME/.claude/metrics}/$SID"

python3 "${HOOK_DIR}/_lib/tool-timing-emit.py" \
  "$DIR" "$TS" "$TOOL" "$DURATION" "$SUCCESS" "$ROLE" "$TASK" 2>/dev/null || true
exit 0

#!/usr/bin/env bash
# Tool output-bytes telemetry — PostToolUse + PostToolUseFailure hook.
# Writes one JSONL line per tool call to metrics/{session}/tool-output-bytes.jsonl
# capturing char_count + estimated_tokens of tool_response.output. When
# estimated_tokens > 20000, emits a stderr warning. Never exits non-zero.
# Sibling of tool-timing-capture.sh — separate concern (output size vs duration),
# separate retire path. JSON emission goes through a Python helper —
# never bash printf for dynamic values (load-bearing learned instinct).
#
# enforces: protocols/agent-protocol.md:Resource Bounds
# protects: pipeline, forensics

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PostToolUse"
trap 'log_hook_event $?' EXIT

[[ "${CLAUDE_DISABLE_TOOL_OUTPUT_BYTES:-0}" == "1" ]] && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
TASK="${CLAUDE_PIPELINE_TASK_ID:-}"

SID_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SID="${SID_RAW//[^A-Za-z0-9_-]/}"
[[ -z "$SID" ]] && SID="local-$$"
DIR="${CLAUDE_HOOK_LOG_DIR:-$HOME/.claude/metrics}/$SID"

printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/tool-output-bytes-emit.py" \
  "$DIR" "$TS" "$TASK" || true
exit 0

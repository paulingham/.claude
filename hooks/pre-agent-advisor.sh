#!/usr/bin/env bash
# Pre-Agent Advisor-Mode — PreToolUse hook for Agent matcher (Path B, log-only).
# Resolves would-be Sonnet+Opus-advisor pairing for reviewer spawns and logs to
# ~/.claude/metrics/{session}/advisor-dispatch.jsonl. Does NOT block: the Agent
# tool input schema does not currently expose `advisor`, so enforcement is
# deferred until the schema lands. Mirrors pre-agent-thinking.sh shape.

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-advisor.py" 2>/dev/null) || exit 0
DECISION=$(printf '%s\n' "$OUT" | sed -n '1p')
RESOLVED=$(printf '%s\n' "$OUT" | sed -n '2p')

[[ "$DECISION" == "LOG" ]] || exit 0

SESSION_RAW="${CLAUDE_SESSION_ID:-local-$$}"
SESSION="${SESSION_RAW//[^A-Za-z0-9_-]/_}"
[[ -z "$SESSION" || "$SESSION" =~ ^_+$ ]] && SESSION="local-$$"
CLAUDE_SESSION_ID="$SESSION" \
  bash "${HOOK_DIR}/_lib/log-injection.sh" "$INPUT" "$RESOLVED" "logged" "advisor-dispatch.jsonl" 2>/dev/null
exit 0

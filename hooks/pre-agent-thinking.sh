#!/usr/bin/env bash
# Pre-Agent Thinking Defaults — PreToolUse hook for Agent matcher (Path B, log-only).
# Resolves the would-be defaults for Agent spawns missing tool_input.thinking and
# logs to ~/.claude/metrics/{session}/hook-injections.jsonl. Does NOT block: the
# Agent tool input schema does not currently expose `thinking`, so enforcement is
# deferred until Claude Code lands modified_tool_input support (Path A).
#
# enforces: protocols/thinking-defaults.md:Hook Behavior
# protects: build-implementation, pipeline

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/check-bypass-gate.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

check_bypass_gate "CLAUDE_DISABLE_THINKING_GATE" && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-thinking.py" 2>/dev/null) || exit 0
DECISION=$(printf '%s\n' "$OUT" | sed -n '1p')
RESOLVED=$(printf '%s\n' "$OUT" | sed -n '2p')

[[ "$DECISION" == "LOG" ]] || exit 0
printf '%s' "$INPUT" | bash "${HOOK_DIR}/_lib/log-injection.sh" "" "$RESOLVED" "logged" 2>/dev/null
exit 0

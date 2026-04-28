#!/usr/bin/env bash
# Pre-Agent Thinking Defaults — PreToolUse hook for Agent matcher (Path B, log-only).
# Resolves the would-be defaults for Agent spawns missing tool_input.thinking and
# logs to ~/.claude/metrics/{session}/hook-injections.jsonl. Does NOT block: the
# Agent tool input schema does not currently expose `thinking`, so enforcement is
# deferred until Claude Code lands modified_tool_input support (Path A).

source ~/.claude/hooks/_lib/log.sh
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
trap 'log_hook_event $?' EXIT

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-thinking.py" 2>/dev/null) || exit 0
DECISION=$(printf '%s\n' "$OUT" | sed -n '1p')
RESOLVED=$(printf '%s\n' "$OUT" | sed -n '2p')

[[ "$DECISION" == "LOG" ]] || exit 0
bash "${HOOK_DIR}/_lib/log-injection.sh" "$INPUT" "$RESOLVED" "logged" 2>/dev/null
exit 0

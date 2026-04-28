#!/usr/bin/env bash
# Pre-Agent Instinct Injection — PreToolUse hook for Agent matcher (Path B, log-only).
# Resolves which learned-instincts apply to the spawning agent and logs the
# decision to ~/.claude/metrics/{session}/instinct-injections.jsonl. Does NOT
# block: the Agent tool input schema does not currently expose a way to inject
# prompt content from a hook, so the orchestrator-side caller is responsible
# for the actual prompt-string splice. Mirrors pre-agent-thinking.sh shape.

source ~/.claude/hooks/_lib/log.sh
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
trap 'log_hook_event $?' EXIT

[[ "${CLAUDE_DISABLE_INSTINCT_INJECTION:-0}" == "1" ]] && exit 0

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-instincts.py" 2>/dev/null
exit 0

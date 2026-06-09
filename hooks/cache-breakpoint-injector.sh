#!/usr/bin/env bash
# Prompt-Caching Breakpoint Injector — PreToolUse hook for Agent matcher.
# Path-B advisory/log-only at v2.1.140: resolves cache_control anchor positions
# and logs to ~/.claude/metrics/{session}/cache-injections.jsonl. Does NOT
# mutate tool_input.prompt (the Agent input schema does not currently expose
# `modified_tool_input` for cache_control; enforcement is deferred until
# Claude Code lands the schema flip — see line 28-29 for the one-line surface
# that promotes this hook from log-only to mutation).
#
# enforces: protocols/cost-discipline.md:Prompt-Caching Breakpoint Work
# protects: pipeline

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
source "${HOOK_DIR}/_lib/agent-injection-capability.sh"
agent_injection_supported || exit 0
OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-cache-breakpoints.py" 2>/dev/null) || exit 0
DECISION=$(printf '%s\n' "$OUT" | sed -n '1p')
RESOLVED=$(printf '%s\n' "$OUT" | sed -n '2p')

[[ "$DECISION" == "LOG" ]] || exit 0
printf '%s' "$INPUT" | bash "${HOOK_DIR}/_lib/log-injection.sh" "" "$RESOLVED" "logged" cache-injections.jsonl 2>/dev/null
exit 0

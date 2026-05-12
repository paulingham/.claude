#!/usr/bin/env bash
# Pre-Agent Tool Allowlist — PreToolUse hook for Agent matcher (Path B, log-only).
# Resolves would-be subset check between requested allowed_tools and agent
# frontmatter tools, logs to ~/.claude/metrics/{session}/tool-allowlist.jsonl.
# Does NOT block: the Agent tool input schema does not currently expose
# `allowed_tools`, so enforcement is deferred until the schema lands. Mirrors
# pre-agent-thinking.sh / pre-agent-advisor.sh shape.
#
# enforces: protocols/agent-protocol.md:Per-Agent Tool Scoping
# protects: all-agent-spawning-skills

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

[[ "${CLAUDE_DISABLE_TOOL_ALLOWLIST:-0}" == "1" ]] && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-tool-allowlist.py" 2>/dev/null) || exit 0
DECISION=$(printf '%s\n' "$OUT" | sed -n '1p')
RESOLVED=$(printf '%s\n' "$OUT" | sed -n '2p')
FRONTMATTER=$(printf '%s\n' "$OUT" | sed -n '3p')

[[ "$DECISION" == "LOG" ]] || exit 0
bash "${HOOK_DIR}/_lib/log-allowlist.sh" "$INPUT" "$RESOLVED" "$FRONTMATTER" 2>/dev/null
exit 0

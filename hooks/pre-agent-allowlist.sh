#!/usr/bin/env bash
# Pre-Agent Tool Allowlist — PreToolUse hook for Agent matcher (Path B, log-only).
# Resolves would-be subset check between requested allowed_tools and agent
# frontmatter tools, logs to ~/.claude/metrics/{session}/tool-allowlist.jsonl.
# Does NOT block: the Agent tool input schema does not currently expose
# `allowed_tools`, so enforcement is deferred until the schema lands. Mirrors
# pre-agent-thinking.sh / pre-agent-advisor.sh shape.

[[ "${CLAUDE_DISABLE_TOOL_ALLOWLIST:-0}" == "1" ]] && exit 0

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-tool-allowlist.py" 2>/dev/null) || exit 0
DECISION=$(printf '%s\n' "$OUT" | sed -n '1p')
RESOLVED=$(printf '%s\n' "$OUT" | sed -n '2p')
FRONTMATTER=$(printf '%s\n' "$OUT" | sed -n '3p')

[[ "$DECISION" == "LOG" ]] || exit 0
bash "${HOOK_DIR}/_lib/log-allowlist.sh" "$INPUT" "$RESOLVED" "$FRONTMATTER" 2>/dev/null
exit 0

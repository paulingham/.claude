#!/usr/bin/env bash
# Pre-Agent Tool Allowlist — PreToolUse hook for Agent matcher (ENFORCING).
# Resolves subset check between requested allowed_tools and agent frontmatter
# tools. When the resolver returns action="would_block", the hook logs the
# violation to ~/.claude/metrics/{session}/tool-allowlist.jsonl, prints a
# stderr "BLOCKED:" line, and exits 2 — denying the spawn.
#
# Promotion criterion satisfied 2026-05-14: pure-deny path requires no
# `modified_tool_input` schema; the existing `exit 2 + stderr` idiom shared
# by hooks/main-branch-guard.sh, hooks/agent-skill-reminder.sh, etc. blocks
# Agent spawns today. Rollback: swap `exit 2` → `exit 0` on the block branch,
# or set CLAUDE_DISABLE_TOOL_ALLOWLIST=1 at runtime.
#
# DEPENDS ON: hooks/_lib/resolve-tool-allowlist.py line-2 stdout = JSON dict
# with key "action" ∈ {skip, advisory, ok, would_block}. If the resolver's
# stdout shape changes, the jq parse below returns empty and the hook
# silently fails open (exit 0).
#
# enforces: protocols/agent-protocol.md:Per-Agent Tool Scoping
# protects: all-agent-spawning-skills

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/check-bypass-gate.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:Agent"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

check_bypass_gate "CLAUDE_DISABLE_TOOL_ALLOWLIST" && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)
OUT=$(printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/resolve-tool-allowlist.py" 2>/dev/null) || exit 0
DECISION=$(printf '%s\n' "$OUT" | sed -n '1p')
RESOLVED=$(printf '%s\n' "$OUT" | sed -n '2p')
FRONTMATTER=$(printf '%s\n' "$OUT" | sed -n '3p')

[[ "$DECISION" == "LOG" ]] || exit 0

ACTION=$(printf '%s' "$RESOLVED" | jq -r '.action // empty' 2>/dev/null)
if [[ "$ACTION" == "would_block" ]]; then
  OFFENDING=$(printf '%s' "$RESOLVED" | jq -c '.offending_tools // []' 2>/dev/null)
  BLOCKED_RESOLVED=$(printf '%s' "$RESOLVED" | jq -c '.action = "blocked"' 2>/dev/null)
  bash "${HOOK_DIR}/_lib/log-allowlist.sh" "$INPUT" "$BLOCKED_RESOLVED" "$FRONTMATTER" 2>/dev/null
  printf 'BLOCKED: tool-allowlist subset violation — subagent=%s offending=%s\n' \
    "$SUBAGENT_TYPE" "$OFFENDING" >&2
  exit 2
fi

bash "${HOOK_DIR}/_lib/log-allowlist.sh" "$INPUT" "$RESOLVED" "$FRONTMATTER" 2>/dev/null
exit 0

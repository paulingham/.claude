#!/usr/bin/env bash
# Over-spawn guard — PreToolUse hook for Agent matcher.
# Scores per-session phase fan-out against slice-count-aware ceiling,
# LOGS warn records to JSONL, NEVER blocks or modifies spawn (advisory only).
#
# INVARIANT 1: stdout is ALWAYS empty — no modified_tool_input ever emitted.
# INVARIANT 2: exit 0 ALWAYS — never blocks an Agent spawn.
#
# enforces: protocols/autonomous-intelligence.md — advisory-first
# protects: pipeline phase fan-out observability

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/check-bypass-gate.sh"

check_bypass_gate "CLAUDE_DISABLE_OVER_SPAWN_GUARD" && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)

printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/over_spawn_guard.py" 2>/dev/null || exit 0

exit 0

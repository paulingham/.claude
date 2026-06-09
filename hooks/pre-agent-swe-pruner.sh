#!/usr/bin/env bash
# SWE-Pruner advisory context-pruning filter — PreToolUse hook for Agent matcher.
# Scores orchestrator-assembled spawn prompt for relevance to agent's goal,
# LOGS proposed drops to JSONL, NEVER mutates the prompt (advisory only).
#
# INVARIANT 1: stdout is ALWAYS empty — no modified_tool_input ever emitted.
# INVARIANT 2: exit 0 ALWAYS — never blocks an Agent spawn.
#
# enforces: protocols/autonomous-intelligence.md — advisory-first (MM1)
# protects: spawn context integrity

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/check-bypass-gate.sh"

check_bypass_gate "CLAUDE_DISABLE_SWE_PRUNER" && exit 0

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0

INPUT=$(cat)

printf '%s' "$INPUT" | python3 "${HOOK_DIR}/_lib/swe_pruner_main.py" \
    "${HOOK_DIR}/_lib" \
    2>/dev/null || exit 0

exit 0

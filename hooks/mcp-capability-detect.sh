#!/usr/bin/env bash
# mcp-capability-detect.sh — SessionStart hook
# enforces: plan.md § ADVISORY not fail-closed
# protects: all pipeline phases (hints capability; never stops a pipeline)
#
# WHY — DUAL REGISTRATION REQUIRED:
# Every hook must appear in BOTH registries or it will not fire:
#   hooks/hooks.json   — loaded when Claude Code runs from the install dir
#   settings.json      — loaded when running from any other directory
# The idiom for both registries is identical:
#   h="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/mcp-capability-detect.sh"
#   [ -x "$h" ] && exec "$h" || exit 0
# Run `scripts/new-hook.sh mcp-capability-detect <Event>` to auto-wire both registries
# and run the 12-AC registration invariant to verify.
#
# WHY — SESSION ID FROM STDIN NOT ENV:
# CLAUDE_SESSION_ID is unset in hook env. Derive it from the JSON payload:
#   SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

HOOK_ROOT="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"

source "$HOOK_ROOT/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SessionStart"
trap 'log_hook_event $?' EXIT

source "$HOOK_ROOT/hooks/hook-profile.sh" \
  && check_hook_profile "standard" || exit 0
source "$HOOK_ROOT/hooks/loop-guard.sh" \
  && check_loop_guard "mcp-capability-detect" || exit 0

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

MCP_RAW=$(claude mcp list 2>/dev/null || true)

# WHY: On failure/empty → write all-absent manifest, still exit 0.
# This is ADVISORY only — a detection failure must never block a pipeline.
python3 "$HOOK_ROOT/hooks/_lib/mcp_capability_cli.py" \
    --session-id "$SESSION_ID" \
    --hook-root "$HOOK_ROOT" \
    --input "${MCP_RAW:-}" 2>/dev/null || true

exit 0

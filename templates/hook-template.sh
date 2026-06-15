#!/usr/bin/env bash
# your-hook-name.sh — <PostToolUse|PreToolUse|PostCompact|Stop> hook
# enforces: <cite the rule this hook protects, e.g. rules/core.md § Code Shape Rules>
# protects: <cite the pipeline phase(s) this guards, e.g. build, ship>
#
# WHY — DUAL REGISTRATION REQUIRED:
# Every hook must appear in BOTH registries or it will not fire:
#   hooks/hooks.json   — loaded when Claude Code runs from the install dir
#   settings.json      — loaded when running from any other directory
# The idiom for both registries is identical:
#   h="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/your-hook-name.sh"
#   [ -x "$h" ] && exec "$h" || exit 0
# Run `scripts/new-hook.sh your-hook-name <Event>` to auto-wire both registries
# and run the 12-AC registration invariant to verify.
#
# WHY — SESSION ID FROM STDIN NOT ENV:
# CLAUDE_SESSION_ID is unset in hook env. Derive it from the JSON payload:
#   SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "${TOOL_NAME:-unknown}"
trap 'log_hook_event $?' EXIT

source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" \
  && check_hook_profile "standard" || exit 0
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/loop-guard.sh" \
  && check_loop_guard "your-hook-name" || exit 0

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

# WHY: implement your guard logic here then exit with the appropriate code:
#   exit 0  — allow (advisory hooks always exit 0)
#   exit 2  — hard block (blocking hooks that prevent the tool call)
exit 0

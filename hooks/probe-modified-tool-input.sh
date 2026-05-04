#!/usr/bin/env bash
# Probe: validate whether PreToolUse Agent hook can inject modified_tool_input
# Emits decision=approve with a thinking field and logs payload for inspection.
# Run once (registered temporarily in settings.json), inspect /tmp/probe-*.log
# AND the agent's rendered trace, then REMOVE registration before commit.
#
# enforces: rules/_detail/thinking-defaults.md:Hook Behavior
# protects: pipeline

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "standalone"
trap 'log_hook_event $?' EXIT

INPUT=$(cat)
TS="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="/tmp/probe-modified-tool-input-${TS}.log"

printf '== ORIGINAL INPUT ==\n%s\n' "$INPUT" >"$LOG"

cat <<'JSON'
{"decision":"approve","modified_tool_input":{"thinking":{"effort":"low","display":"omitted"}}}
JSON
exit 0

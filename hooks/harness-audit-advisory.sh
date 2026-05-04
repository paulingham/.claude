#!/usr/bin/env bash
# Harness audit advisory — fast health check at SessionStart (≤2s budget)
# enforces: rules/core.md:Iron Laws
# protects: harness-audit
# Sources _lib/harness-audit-fast.sh; never invokes skill /harness-audit.

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SessionStart"
trap 'log_hook_event $?' EXIT

source "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/_lib/harness-audit-fast.sh" 2>/dev/null

RESULT=$(_haf_run_all 2>/dev/null)
CRITICALS=$(echo "$RESULT" | grep -oE 'criticals=[0-9]+' | cut -d= -f2)
WARNINGS=$(echo "$RESULT" | grep -oE 'warnings=[0-9]+' | cut -d= -f2)

if [[ "${CRITICALS:-0}" -gt 0 || "${WARNINGS:-0}" -gt 3 ]]; then
  echo "HARNESS ADVISORY: ${CRITICALS:-0} critical, ${WARNINGS:-0} warnings — run /harness-audit for full report" >&2
fi

exit 0

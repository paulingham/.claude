#!/usr/bin/env bash
# Auto Reduce Permissions — Stop event hook.
# Periodically (default: every 7 days) launches a headless Claude session that
# runs the /fewer-permission-prompts skill non-interactively. The skill scans
# recent transcripts for repeated read-only tool calls and appends prioritized
# allowlist entries to ~/.claude/settings.json, reducing future permission
# prompts.
#
# Advisory only — never blocks. Exits 0 unconditionally.
#
# Environment overrides (primarily for tests):
#   CLAUDE_REDUCE_PERMISSIONS_STATE_FILE    Path to last-run timestamp file
#   CLAUDE_REDUCE_PERMISSIONS_LOG_FILE      Path to log file
#   CLAUDE_REDUCE_PERMISSIONS_INTERVAL_DAYS Days between runs (default 7)
#   CLAUDE_REDUCE_PERMISSIONS_DRY_RUN       If "1", log what would happen and
#                                           skip the actual claude invocation
#   CLAUDE_HOOK_PROFILE=minimal             Skip the hook entirely

set -uo pipefail
# Deliberately omitting -e: advisory-only, individual failures must not abort.

source ~/.claude/hooks/hook-profile.sh && check_hook_profile "standard" || exit 0

STATE_FILE="${CLAUDE_REDUCE_PERMISSIONS_STATE_FILE:-$HOME/.claude/automation/.permission-reducer-last-run}"
LOG_FILE="${CLAUDE_REDUCE_PERMISSIONS_LOG_FILE:-$HOME/.claude/automation/logs/permission-reducer.log}"
INTERVAL_DAYS="${CLAUDE_REDUCE_PERMISSIONS_INTERVAL_DAYS:-7}"
DRY_RUN="${CLAUDE_REDUCE_PERMISSIONS_DRY_RUN:-0}"

INPUT=$(cat 2>/dev/null || echo "{}")
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")" 2>/dev/null || true

NOW=$(date +%s)
INTERVAL_SECS=$(( INTERVAL_DAYS * 86400 ))

if [ -f "$STATE_FILE" ]; then
  LAST_RUN=$(cat "$STATE_FILE" 2>/dev/null || echo "0")
  case "$LAST_RUN" in
    ''|*[!0-9]*) LAST_RUN=0 ;;
  esac
  ELAPSED=$(( NOW - LAST_RUN ))
  if [ "$ELAPSED" -lt "$INTERVAL_SECS" ]; then
    exit 0
  fi
fi

_log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG_FILE"
}

_spawn_reducer() {
  local claude_bin
  claude_bin=$(command -v claude 2>/dev/null || echo "claude")
  nohup "$claude_bin" -p "/fewer-permission-prompts" \
    --permission-mode bypassPermissions \
    --dangerously-skip-permissions \
    >> "$LOG_FILE" 2>&1 </dev/null &
  disown 2>/dev/null || true
}

if [ "$DRY_RUN" = "1" ]; then
  _log "DRY_RUN: would spawn claude -p /fewer-permission-prompts (interval=${INTERVAL_DAYS}d)"
else
  _log "Spawning claude -p /fewer-permission-prompts (interval=${INTERVAL_DAYS}d)"
  _spawn_reducer
fi

echo "$NOW" > "$STATE_FILE"
exit 0

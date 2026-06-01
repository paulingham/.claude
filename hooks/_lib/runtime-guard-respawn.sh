#!/usr/bin/env bash
# Re-spawn cap helpers for runtime-guard. Bash-3.2 clean.
# Source after runtime-guard-key.sh and resource-bounds.sh.
#
# Counter file is sibling of <key>.start: subagent-runtimes/<key>.count.
# Lifecycle: written/incremented at PreToolUse:Agent; NOT cleared by
# SubagentStop (only .start is). Cleared with pipeline-state at Reflect.

_rg_active_task_id() {
  local d="${CLAUDE_PIPELINE_STATE_DIR:-$HARNESS_DATA/pipeline-state}" f
  [ -d "$d" ] || { printf 'unknown'; return 0; }
  f=$(grep -rl "verdict: in_progress" "$d" 2>/dev/null | head -1)
  [ -z "$f" ] && { printf 'unknown'; return 0; }
  grep "^task_id:" "$f" 2>/dev/null | head -1 | sed 's/task_id: *//' | tr -d ' '
}

_rg_compute_respawn_key() {
  local stype="$1" tid="$2" hasher
  hasher=$(_rg_hasher)
  [ -z "$hasher" ] && { printf 'unknown'; return 0; }
  printf '%s|%s' "$stype" "$tid" | "$hasher" 2>/dev/null | awk '{print $1}'
}

_rg_respawn_path() {
  printf '%s/%s.count' "$1" "$2"
}

_rg_increment_respawn() {
  local f="$1" cur=0
  [ -f "$f" ] && cur=$(cat "$f" 2>/dev/null | tr -d ' \n')
  case "$cur" in ''|*[!0-9]*) cur=0 ;; esac
  cur=$((cur + 1))
  printf '%s' "$cur" > "$f" 2>/dev/null
  printf '%s' "$cur"
}

_rg_emit_respawn_block() {
  printf 'BLOCKED: re-dispatch cap exceeded subagent_type=%s task_id=%s count=%s max=%s\nThe orchestrator must escalate to the user instead of re-spawning this role.\nSee rules/operational-protocol.md > Error Recovery Principles.\n' \
    "$1" "$2" "$3" "$4" >&2
}

#!/usr/bin/env bash
# Worktree-cwd-check — SubagentStop diagnostic. Never blocks (always exit 0).
# Pairs prevented→post-confirmed via per-task cursor; drift-detected if HEAD!=main.
#
# enforces: protocols/agent-protocol.md:Main-Branch Invariant
# protects: build-implementation, pipeline
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/_lib/harness-paths.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/log.sh"
_log_hook_start
_log_hook_trigger "SubagentStop"
trap 'log_hook_event $?' EXIT

set -uo pipefail
INPUT=$(cat 2>/dev/null) || INPUT=""
[ "$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ] && exit 0
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/hook-profile.sh" && check_hook_profile "minimal" || exit 0
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/main-branch-detect.sh"
source "${CLAUDE_PLUGIN_ROOT:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/hooks/_lib/worktree-cwd-pairing.sh"

_wcc_resolve_task_id() {
  local id="${CLAUDE_PIPELINE_TASK_ID:-}" f
  [[ -n "$id" ]] && { printf '%s' "$id"; return; }
  f=$(grep -rl "verdict: in_progress" "$HARNESS_DATA/pipeline-state" 2>/dev/null | head -1)
  [[ -n "$f" ]] && awk '/^task_id:/ {sub(/task_id: */,""); print; exit}' "$f"
}

_wcc_emit_record() {
  local src="$1" extra="${2:-}" ts; ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  jq -nc --arg ts "$ts" --arg sid "$SESSION" --arg tid "$TASK_ID" --arg src "$src" --arg extra "$extra" \
    '{timestamp:$ts,session_id:$sid,task_id:$tid,source:$src} + (if $extra=="" then {} else {current_head:$extra} end)'
}

_wcc_drift_check() {
  local repo_root="${CLAUDE_REPO_ROOT:-$HARNESS_DATA}" head
  head=$(git -C "$repo_root" rev-parse --abbrev-ref HEAD 2>/dev/null) || return 0
  [[ "$head" == "main" ]] && return 0
  mkdir -p "$(dirname "$LOG")" 2>/dev/null
  _wcc_emit_record "drift-detected" "$head" >> "$LOG"
}

TASK_ID="$(_wcc_resolve_task_id)"; TASK_ID="${TASK_ID//[^a-zA-Z0-9_.-]/}"
[[ -z "$TASK_ID" ]] && exit 0
SESSION="${CLAUDE_SESSION_ID:-local-$$}"; SESSION="${SESSION//[^a-zA-Z0-9_.-]/}"
SESSION="${SESSION:-local-$$}"
LOG="$HARNESS_DATA/metrics/$SESSION/main-branch-violations.jsonl"
mkdir -p "$HARNESS_DATA/state" 2>/dev/null
CURSOR="$HARNESS_DATA/state/worktree-cwd-check-cursor-${TASK_ID}"
[[ -f "$LOG" ]] && _wcc_pair_prevented "$CURSOR" "$LOG"
_wcc_drift_check; exit 0

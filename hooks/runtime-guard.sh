#!/usr/bin/env bash
# Runtime guard — PreToolUse Agent|Bash|Write|Edit hook.
# Mode A (Agent): record start file. Mode B (Bash|Write|Edit): scan for over-cap.
# Read intentionally excluded (highest-volume, fast-bounded).
# See rules/agent-protocol.md > Resource Bounds.
# Historical per-call durations are captured separately by hooks/tool-timing-capture.sh
# to metrics/{session}/tool-timings.jsonl. This guard owns wall-clock cap ENFORCEMENT only.
#
# enforces: rules/_detail/agent-protocol.md:Resource Bounds
# protects: pipeline, all-skills

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/log.sh"
_log_hook_start
_log_hook_trigger "PreToolUse:${TOOL_NAME:-Bash}"
SUBAGENT_TYPE=""
trap 'log_hook_event $? "$SUBAGENT_TYPE"' EXIT

set -uo pipefail

# shellcheck source=/dev/null
source "${HOOK_DIR}/hook-profile.sh" && check_hook_profile "standard" || exit 0
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/resource-bounds.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-key.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-respawn.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-record.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-emit.sh"
# shellcheck source=/dev/null
source "${HOOK_DIR}/_lib/runtime-guard-check.sh"

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
SUBAGENT_TYPE=$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null)

_rg_runtime_dir() {
  local sid="${CLAUDE_SESSION_ID:-local-$$}"; sid="${sid//[^a-zA-Z0-9_.-]/}"
  echo "$HOME/.claude/metrics/${sid:-local-$$}/subagent-runtimes"
}

_rg_extract_inputs() {
  echo "$INPUT" | jq -r '"\(.tool_input.subagent_type // "")|\(.tool_input.name // "")|\(.tool_input.team_name // "")"'
}

_rg_check_cap() {
  local stype="$1" tid count max key
  tid=$(_rg_active_task_id)
  key=$(_rg_compute_respawn_key "$stype" "$tid")
  count=$(_rg_increment_respawn "$(_rg_respawn_path "$(_rg_runtime_dir)" "$key")")
  max=$(_max_respawn_count)
  [ "$count" -gt "$max" ] || return 0
  _rg_emit_respawn_block "$stype" "$tid" "$count" "$max"; return 2
}

_rg_record() {
  local stype name team
  IFS='|' read -r stype name team <<< "$(_rg_extract_inputs)"
  mkdir -p "$(_rg_runtime_dir)" 2>/dev/null
  _rg_check_cap "$stype" || exit 2
  _rg_write_start "$(_rg_runtime_dir)" "$(_rg_compute_key "$stype")" "$(_rg_class_of "$team")" "${name:-$stype}"
}

_rg_dispatch() {
  case "$TOOL_NAME" in
    Agent) _rg_record; exit 0 ;;
    Bash|Write|Edit) _rg_scan_dir "$(_rg_runtime_dir)" || exit 2; exit 0 ;;
    *) exit 0 ;;
  esac
}

_rg_dispatch

#!/usr/bin/env bash
# Dispatch + record/check helpers for runtime-guard.sh (extracted to keep the
# hook entry-point ≤50 LOC). Depends on the sibling runtime-guard-* libs +
# resource-bounds.sh already being sourced by the caller. Reads the global
# INPUT / TOOL_NAME set by the hook.

_rg_runtime_dir() {
  local sid="${CLAUDE_SESSION_ID:-local-$$}"; sid="${sid//[^a-zA-Z0-9_.-]/}"
  echo "$HARNESS_DATA/metrics/${sid:-local-$$}/subagent-runtimes"
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

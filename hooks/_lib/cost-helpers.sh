#!/usr/bin/env bash
# Shared helpers for cost-feed.sh (SubagentStop hook).
# Bash-3.2 clean. Every function body ≤5 lines. POSIX O_APPEND atomic for <4096B records.
# Field path verified from subagent-stop-trajectory.sh: SubagentStop top-level fields
# are .subagent_type / .subagent_id (NO .tool_input wrapper). Token usage assumed at
# .usage.input_tokens (top level), matching that asymmetry.

_cf_pipeline_id_from_path() {
  # New: parent dir. Legacy: basename minus '-pipeline.md'.
  case "$(basename "$1")" in
    pipeline.md) basename "$(dirname "$1")" ;;
    *) local base; base=$(basename "$1"); echo "${base%-pipeline.md}" ;;
  esac
}

_cf_pipeline_id() {
  # DUAL_PATH: helper finds new-layout {task}/pipeline.md AND legacy {task}-pipeline.md.
  source "$(dirname "${BASH_SOURCE[0]}")/pipeline-state-paths.sh"
  local newest; newest=$(_psp_find_active_pipelines | head -1)
  [ -z "$newest" ] && { echo "none"; return 0; }
  _cf_pipeline_id_from_path "$newest"
}

_cf_session_id() {
  local sid="${CLAUDE_SESSION_ID:-unknown}"
  echo "${sid//[^A-Za-z0-9_-]/}"
}

_cf_resolve_field() {
  # _cf_resolve_field <input> <jq_path> <env_fallback>
  local val
  val=$(echo "$1" | jq -r "$2 // empty" 2>/dev/null)
  [ -n "$val" ] && { echo "$val"; return 0; }
  echo "${3:-unknown}"
}

_cf_token() {
  # _cf_token <input> <field_name>
  local v
  v=$(echo "$1" | jq -r ".usage.$2 // 0" 2>/dev/null)
  case "$v" in ''|*[!0-9]*) echo 0 ;; *) echo "$v" ;; esac
}

_cf_compute_cost() {
  # _cf_compute_cost <input_tokens> <output_tokens> <cached_tokens>
  jq -n --argjson i "$1" --argjson o "$2" --argjson c "$3" \
    '(($i * 5) + ($o * 25) + ($c * 0.5)) / 1000000' 2>/dev/null
}

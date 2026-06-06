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

_cf_graph_depth() {
  # echo bare int from CLAUDE_SUBAGENT_DEPTH, or literal "null" sentinel.
  local raw="${CLAUDE_SUBAGENT_DEPTH:-}"
  case "$raw" in ''|*[!0-9]*) echo null ;; *) echo "$raw" ;; esac
}

_cf_prior_error_count() {
  # No robust envelope/state source; default 0 (documented decision).
  echo 0
}

_cf_router_decision() {
  # "none" until Story 2 populates the would-be tier.
  echo none
}

_cf_intake_from_path() {
  # New: sibling intake.md. Legacy: '{task}-pipeline.md' -> '{task}-intake.md'.
  case "$(basename "$1")" in
    pipeline.md) echo "$(dirname "$1")/intake.md" ;;
    *) local base; base=$(basename "$1"); echo "$(dirname "$1")/${base%-pipeline.md}-intake.md" ;;
  esac
}

_cf_active_intake_path() {
  # Resolve the active pipeline (same dual-path logic as _cf_pipeline_id) -> intake.md.
  source "$(dirname "${BASH_SOURCE[0]}")/pipeline-state-paths.sh"
  local newest; newest=$(_psp_find_active_pipelines | head -1)
  [ -z "$newest" ] && return 1
  _cf_intake_from_path "$newest"
}

_cf_budget_from_file() {
  # First integer from flat `complexity_budget: N` or nested `total: N`; else non-zero.
  [ -r "$1" ] || return 1
  local n; n=$(grep -E '^complexity_budget:[[:space:]]*[0-9]|^[[:space:]]*total:[[:space:]]*[0-9]' "$1" 2>/dev/null \
    | grep -oE '[0-9]+' | head -1)
  [ -n "$n" ] && { echo "$n"; return 0; } || return 1
}

_cf_complexity_budget() {
  # Resolve active intake.md, read nested total: or flat complexity_budget: N.
  local f; f=$(_cf_active_intake_path) || { echo null; return 0; }
  _cf_budget_from_file "$f" 2>/dev/null || echo null
}

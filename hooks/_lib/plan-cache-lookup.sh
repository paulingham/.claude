#!/usr/bin/env bash
# plan-cache-lookup helpers (Slice B — MISS-only).
# Plan: pipeline-state/plan-cache-agentic/plan.md § slice-b-skill-miss-only.
# Slice B ships a MISS-only lookup procedure + mode resolver default `off`
# (LOW-eng-3 partial-merge safety). HIT path lands in Slice C.
#
# Public functions: _plan_cache_mode, _plan_cache_dir, _plan_cache_lookup.

_PLAN_CACHE_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./project-hash.sh
source "$_PLAN_CACHE_LIB_DIR/project-hash.sh"
# shellcheck source=./repo-hash.sh
source "$_PLAN_CACHE_LIB_DIR/repo-hash.sh"
# Note: pipeline-state-paths.sh (_psp_find_active_pipelines) is sourced and
# invoked by the orchestrator at lookup time to discover task_id; the lib
# itself takes (task_class, tier, critical) and does not need that import.

_plan_cache_mode() {
  case "${CLAUDE_PLAN_CACHE_MODE:-off}" in
    off|shadow|on) printf '%s\n' "${CLAUDE_PLAN_CACHE_MODE:-off}" ;;
    *) printf 'off\n' ;;
  esac
}

_plan_cache_dir() {
  local hash="${CLAUDE_PROJECT_HASH:-}"
  [[ -z "$hash" ]] && hash=$(_project_hash --fallback "$(basename "$(pwd)")")
  printf '%s/learning/%s/plans\n' "${HOME:-$PWD}" "$hash"
}

# _plan_cache_lookup task_class tier critical -> JSON verdict on stdout.
# task_id is discovered from the active pipeline via _psp_find_active_pipelines.
_plan_cache_lookup() {
  local task_class="$1" tier="$2" critical="$3"
  local mode key dir
  mode=$(_plan_cache_mode)
  [[ "$mode" == "off" ]] && { _plan_cache_emit_miss disabled ""; return; }
  key=$(_plan_cache_key "$task_class" "$(_repo_hash)" "$tier" "$critical") || return 1
  dir=$(_plan_cache_dir)
  [[ -f "$dir/$key.md" ]] || { _plan_cache_emit_miss no-template "$key"; return; }
  # Slice B MISS-only: HIT path lands in Slice C. Until then, key-present = MISS.
  _plan_cache_emit_miss shadow-mode "$key"
}

_plan_cache_emit_miss() {
  local reason="$1" key="$2"
  printf '{"verdict":"PLAN_CACHE_MISS","reason":"%s","cache_key":"%s"}\n' \
    "$reason" "$key"
}

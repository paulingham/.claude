#!/usr/bin/env bash
# Case metadata resolver. Reads scoring_mode from eval/cases/<id>/metadata.json;
# falls back to test-passing when unset, missing, or invalid.

_cases_dir() { printf '%s' "${EVAL_CASES_DIR:-$PWD/eval/cases}"; }

_valid_mode() {
  case "$1" in exact|normalized|test-passing) return 0 ;; *) return 1 ;; esac
}

resolve_scoring_mode() {
  local meta="$(_cases_dir)/$1/metadata.json" mode
  [ -r "$meta" ] || { echo test-passing; return; }
  mode="$(jq -r '.scoring_mode // "test-passing"' "$meta" 2>/dev/null)"
  _valid_mode "$mode" && { echo "$mode"; return; }
  echo test-passing
}

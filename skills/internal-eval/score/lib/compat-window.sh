#!/usr/bin/env bash
# Harness-ref compatibility window per case (plan B5).
# A case is compatible with run_sha iff:
#   git merge-base --is-ancestor min_sha run_sha (run is at-or-after min)
#   AND (max_sha is null OR git merge-base --is-ancestor run_sha max_sha,
#        meaning run is at-or-before max)
# If min/max are empty / "null" / missing, the bound is treated as unbounded.

# case_compatible <case-metadata.json> <run-sha> <repo>
case_compatible() {
  local meta="$1"; local run_sha="$2"; local repo="$3"
  [ -f "$meta" ] || return 0
  local min max
  min="$(jq -r '.min_harness_ref // empty' "$meta")"
  max="$(jq -r '.max_harness_ref // empty' "$meta")"
  _check_bounds "$repo" "$run_sha" "$min" "$max"
}

_check_bounds() {
  local repo="$1"; local run="$2"; local min="$3"; local max="$4"
  _at_least "$repo" "$run" "$min" || return 1
  _at_most  "$repo" "$run" "$max" || return 1
}

_at_least() {
  [ -z "$3" ] && return 0
  (cd "$1" 2>/dev/null && git merge-base --is-ancestor "$3" "$2") 2>/dev/null
}

_at_most() {
  [ -z "$3" ] || [ "$3" = null ] && return 0
  (cd "$1" 2>/dev/null && git merge-base --is-ancestor "$2" "$3") 2>/dev/null
}

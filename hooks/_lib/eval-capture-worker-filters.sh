#!/usr/bin/env bash
# Filters: contamination date cutoff + oracle-match wrapper + composed gate.
# Sources cache-tier helpers; cache hit avoids gh CLI subprocesses entirely.

_HERE_ECF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$_HERE_ECF/eval-capture-worker-cache.sh"

ECW_CUTOFF="${CLAUDE_EVAL_CAPTURE_CUTOFF:-2026-01-01}"

ecw_date_fresh() {
  local view="$1" merged
  merged="$(printf '%s' "$view" | jq -r '.mergedAt // empty' 2>/dev/null)"
  [ -z "$merged" ] && return 1
  [[ "${merged%%T*}" > "$ECW_CUTOFF" || "${merged%%T*}" == "$ECW_CUTOFF" ]]
}

ecw_oracle_hits() {
  local names="$1" oracle="skills/internal-eval/capture/oracle-paths.json"
  [ -z "$names" ] && return 1
  [ -f "$oracle" ] || return 1
  oracle_match_paths "$oracle" "$names"
}

ecw_fetch_view() {
  ecw_cache_view "$1" && return 0
  gh pr view "$1" --json mergedAt,number,title,body,labels,mergeCommit 2>/dev/null || echo '{}'
}

ecw_fetch_names() {
  ecw_cache_names "$1" && return 0
  gh pr diff "$1" --name-only 2>/dev/null || echo ''
}

ecw_run_filters() {
  local pr="$1" view names
  view="$(ecw_fetch_view "$pr")"
  ecw_date_fresh "$view" || { _ecw_skip "$pr" "merged before cutoff"; return 1; }
  names="$(ecw_fetch_names "$pr")"
  ecw_oracle_hits "$names" || { _ecw_skip "$pr" "no oracle match"; return 1; }
}

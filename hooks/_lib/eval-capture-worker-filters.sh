#!/usr/bin/env bash
# Filters: contamination date cutoff + oracle-match wrapper + composed gate.

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
  gh pr view "$1" --json mergedAt,number,title,body,labels,mergeCommit 2>/dev/null || echo '{}'
}

ecw_run_filters() {
  local pr="$1" view names
  view="$(ecw_fetch_view "$pr")"
  ecw_date_fresh "$view" || { _ecw_skip "$pr" "merged before cutoff"; return 1; }
  names="$(gh pr diff "$pr" --name-only 2>/dev/null || echo '')"
  ecw_oracle_hits "$names" || { _ecw_skip "$pr" "no oracle match"; return 1; }
}

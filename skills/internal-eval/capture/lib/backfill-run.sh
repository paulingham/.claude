#!/usr/bin/env bash
# Orchestrates the backfill. Helpers split across dirs.sh + pr-process.sh.
source "$(dirname "${BASH_SOURCE[0]}")/dirs.sh"
source "$(dirname "${BASH_SOURCE[0]}")/pr-process.sh"

list_merged_prs() {
  gh pr list --state merged --search "merged:>${2}" --limit "$1" \
    --json number,title,labels,mergedAt 2>/dev/null
}

maybe_sparsity_warn() {
  local n; n="$(count_cases)"
  [ "$n" -lt 30 ] && printf 'WARN: only %d cases (<30). Run with --limit higher or hand-author more.\n' "$n" >&2
  return 0
}

backfill_run() {
  local limit="$1" since="$2" cap="$3" excluded=() report
  mkdir -p "$(candidates_dir)" "$(exclusion_dir)"
  iter_prs "$(list_merged_prs "$limit" "$since")" "$cap/oracle-paths.json" excluded
  report="$(exclusion_dir)/.exclusion-report-$(iso_timestamp).md"
  write_exclusion_report "$report" "${excluded[@]:-}"
  maybe_sparsity_warn
}

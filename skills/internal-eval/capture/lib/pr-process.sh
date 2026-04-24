#!/usr/bin/env bash
# PR iteration + exclusion-report writer. Assumes gh_pr_to_case, oracle_match_paths
# and pr_diff_names are already sourced (gh-pr-to-case.sh, oracle-match.sh).

_exclude_line() {
  local pr="$1" names="$2" n
  n="$(printf '%s\n' "$names" | grep -c .)"
  printf 'pr-%s: no oracle match (changed: %d files)' "$pr" "$n"
}

process_pr() {
  local pr="$1" oracle_json="$2" names
  names="$(pr_diff_names "$pr")"
  oracle_match_paths "$oracle_json" "$names" \
    && { gh_pr_to_case "$pr" "$(candidates_dir)" >/dev/null; return 0; }
  _exclude_line "$pr" "$names"; return 1
}

iter_prs() {
  local prs="$1" json="$2" arr_name="$3" pr line
  while IFS= read -r pr; do
    [ -z "$pr" ] && continue
    line="$(process_pr "$pr" "$json")" || eval "$arr_name+=(\"\$line\")"
  done < <(printf '%s' "$prs" | jq -r '.[].number' 2>/dev/null)
}

write_exclusion_report() {
  local report="$1"; shift
  mkdir -p "$(exclusion_dir)"
  { printf '# Backfill Exclusion Report\n\nRun at: %s\n\n' "$(iso_timestamp)"
    printf '%s\n' "$@"; } > "$report"
}

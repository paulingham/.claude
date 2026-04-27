#!/usr/bin/env bash
# Helpers for hooks/no-shell-read.sh. Bash 3.2 SAFE: ERE/awk only.
# Per-clause parsing lives here; path-vs-repo logic in -path.sh.
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/no-shell-read-path.sh"

nsr_split_clauses() {
  printf '%s' "$1" | sed -e 's/&&/;/g' -e 's/||/;/g' \
    | awk 'BEGIN{RS=""} { gsub(/[|;]/, "\n"); print }'
}

nsr_strip_prefix() {
  printf '%s' "$1" | sed -E 's/^[[:space:]]*\(?[[:space:]]*//' \
    | sed -E 's/^([A-Z_][A-Za-z0-9_]*=[^[:space:]]+[[:space:]]+)+//'
}

nsr_first_word() { printf '%s' "$1" | awk '{ print $1; exit }'; }

nsr_is_streaming_tail() {
  printf '%s' "$1" | awk '{ for(i=2;i<=NF;i++) if ($i ~ /^-[fF]$/) exit 0; exit 1 }'
}

nsr_first_path_arg() {
  printf '%s' "$1" | awk '{ for(i=2;i<=NF;i++) if ($i !~ /^-/) { print $i; exit } }'
}

nsr_is_target_cmd() {
  case "$1" in cat|head|tail) return 0 ;; esac; return 1
}

nsr_clause_offender() {
  local stripped cmd
  stripped=$(nsr_strip_prefix "$1")
  cmd=$(nsr_first_word "$stripped")
  nsr_is_target_cmd "$cmd" || return
  [[ "$cmd" == "tail" ]] && nsr_is_streaming_tail "$stripped" && return
  nsr_emit_if_in_repo "$cmd" "$(nsr_first_path_arg "$stripped")" "$2"
}

find_blocking_clause() {
  local clause result
  while IFS= read -r clause; do
    [[ -z "$clause" ]] && continue
    result=$(nsr_clause_offender "$clause" "$2")
    [[ -n "$result" ]] && { printf '%s' "$result"; return 0; }
  done < <(nsr_split_clauses "$1")
}

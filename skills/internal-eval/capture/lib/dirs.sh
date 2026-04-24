#!/usr/bin/env bash
# Path + directory helpers for the capture flow.

iso_timestamp()   { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
candidates_dir()  { printf '%s' "eval/cases/.candidates"; }
exclusion_dir()   { printf '%s' "eval/.candidates"; }

_count_promoted() {
  find eval/cases -maxdepth 1 -mindepth 1 -type d \
    ! -name '_example' ! -name '.candidates' 2>/dev/null | wc -l | tr -d ' '
}

_count_candidates() {
  find eval/cases/.candidates -maxdepth 1 -mindepth 1 -type d 2>/dev/null \
    | wc -l | tr -d ' '
}

count_cases() {
  local n=0
  n=$((n + $(_count_promoted)))
  n=$((n + $(_count_candidates)))
  printf '%d' "$n"
}

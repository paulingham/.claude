#!/usr/bin/env bash
# Oracle path matcher. A path matches iff it hits an include AND no exclude.
set -u

_globs() { jq -r --arg k "$1" '.[$k] // [] | .[]' "$2" 2>/dev/null; }

_match_glob() {
  local path="$1" glob="$2"
  shopt -s extglob 2>/dev/null; shopt -s globstar 2>/dev/null
  [[ "$path" == $glob ]]
}

_hits_any_glob() {
  local path="$1" json="$2" key="$3" g
  while IFS= read -r g; do
    [ -z "$g" ] && continue
    _match_glob "$path" "$g" && return 0
  done < <(_globs "$key" "$json")
  return 1
}

_check_one_path() {
  local path="$1" json="$2"
  _hits_any_glob "$path" "$json" exclude && return 1
  _hits_any_glob "$path" "$json" include
}

oracle_match_paths() {
  local json="$1" paths="$2" p
  while IFS= read -r p; do
    [ -z "$p" ] && continue
    _check_one_path "$p" "$json" && return 0
  done <<<"$paths"
  return 1
}

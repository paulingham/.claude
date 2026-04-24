#!/usr/bin/env bash
# Oracle path matcher. Reads oracle-paths.json, matches a list of file paths.
# Matches if ANY path hits ANY include glob.
set -u

_globs() { jq -r --arg k "$1" '.[$k] // [] | .[]' "$2" 2>/dev/null; }

# Matches a single path against a single bash extglob pattern.
_match_glob() {
  local path="$1" glob="$2"
  shopt -s extglob globstar
  [[ "$path" == $glob ]]
}

_check_one_path() {
  local path="$1" json="$2" g
  while IFS= read -r g; do
    [ -z "$g" ] && continue
    _match_glob "$path" "$g" && return 0
  done < <(_globs include "$json")
  return 1
}

oracle_match_paths() {
  local json="$1" paths="$2" p
  while IFS= read -r p; do
    [ -z "$p" ] && continue
    _check_one_path "$p" "$json" && return 0
  done <<<"$paths"
  return 1
}

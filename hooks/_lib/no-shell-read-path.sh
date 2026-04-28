#!/usr/bin/env bash
# Path resolution for no-shell-read. Bash 3.2 SAFE: no realpath.
# Resolves a (possibly relative) path against $PWD using `cd && pwd`.

nsr_resolve_path() {
  local p="$1" dir base
  case "$p" in /*) printf '%s' "$p"; return ;; esac
  dir=$(dirname "$p"); base=$(basename "$p")
  ( cd "$dir" 2>/dev/null && printf '%s/%s' "$(pwd)" "$base" ) 2>/dev/null
}

nsr_path_in_repo() {
  case "$1" in "$2"|"$2"/*) return 0 ;; esac
  return 1
}

nsr_emit_if_in_repo() {
  local cmd="$1" path="$2" repo_root="$3" abs
  [[ -z "$path" ]] && return
  abs=$(nsr_resolve_path "$path")
  [[ -z "$abs" ]] && return
  nsr_path_in_repo "$abs" "$repo_root" && printf '%s' "$cmd"
}

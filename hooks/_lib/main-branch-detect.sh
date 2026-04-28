#!/usr/bin/env bash
# Main-branch invariant detection. Bash 3.2 SAFE; ERE only. Per-clause check is
# the unit; `cd <path> &&` is the only whole-command early-exit (cd persists
# across `&&`). `git -C`/`--git-dir=` are self-contained per clause. Regexes
# live in main-branch-detect-regex.sh.
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/main-branch-detect-regex.sh"
split_clauses() {
  printf '%s' "$1" | awk 'BEGIN{RS=""} { gsub(/\|\||&&|;|\|/, "\n"); print }'
}
_mbd_fetch_dst_remote_only() {
  printf '%s' "$1" | awk '
    { for(i=1;i<=NF;i++) if($i ~ /:/) { split($i,a,":"); d=a[2];
        if (d == "main" || d == "refs/heads/main") { bad=1; exit }
        if (d !~ /^refs\/remotes\//) { bad=1; exit } } }
    END { exit bad+0 }'
}
_mbd_is_safe_fetch() {
  [[ "$1" =~ git[[:space:]]+fetch[[:space:]] ]] && _mbd_fetch_dst_remote_only "$1"
}
# Safe when last non-flag token after `pull` is empty/origin/upstream/main.
_mbd_is_safe_pull() {
  [[ "$1" =~ git[[:space:]]+pull([[:space:]]|$) ]] || return 1
  local seen=0 b="" t
  for t in $1; do
    [[ "$seen" = 1 && ! "$t" =~ ^- ]] && b="$t"; [[ "$t" = "pull" ]] && seen=1
  done
  [[ -z "$b" || "$b" = "origin" || "$b" = "upstream" || "$b" = "main" ]]
}
is_forbidden_clause() {
  local clause="$1" norm
  [[ "$clause" =~ $(_mbd_wrapper_re) ]] && return 0
  norm=$(_mbd_normalize "$clause")
  [[ "$norm" =~ $(_mbd_forbidden_re) ]] || return 1
  _mbd_is_safe_fetch "$norm" && return 1
  _mbd_is_safe_pull "$norm" && return 1
  return 0
}
_mbd_any_clause_forbidden() {
  local clause
  while IFS= read -r clause; do
    [[ -n "$clause" ]] && is_forbidden_clause "$clause" && return 0
  done < <(split_clauses "$1")
  return 1
}
is_forbidden_command() {
  [[ "$1" =~ $(_mbd_cd_prefix_re) ]] && return 1
  _mbd_any_clause_forbidden "$1"
}
# Test-fixture helpers (is_in_main_tree/is_in_worktree) live in main-branch-detect-fixtures.sh.

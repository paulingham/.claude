#!/usr/bin/env bash
# Main-branch invariant detection library — pure shell, no I/O.
# Bash 3.2 SAFE: no declare -A / mapfile / readarray / ${var,,}; ERE only.
#
# The PER-CLAUSE LOOP is the unit of forbidden-form evaluation, NOT the
# whole command. split_clauses splits on `;`, `&&`, `||`, `|`; each clause
# is then checked standalone — delegation on clause N does NOT carry to N+1.
# Delegation is checked once on the WHOLE command as an early-exit, because
# the delegation regex requires `cd <path> &&` to be intact (split tears it).

_mbd_forbidden_re() {
  printf '%s' '^[[:space:]]*(\(?[[:space:]]*)?(git[[:space:]]+(checkout|switch|branch[[:space:]]+-[dD]|reset[[:space:]]+--hard|merge|rebase|pull)([[:space:]]|$)|git[[:space:]]+fetch[[:space:]]+[^[:space:]]+[[:space:]]+[^[:space:]]+:[^[:space:]]+|git[[:space:]]+push[[:space:]]+[^[:space:]]+[[:space:]]+\+?[^[:space:]]*:(main|refs/heads/main)([[:space:]]|$)|git[[:space:]]+push[[:space:]].*(--delete|[[:space:]]-d)[[:space:]]+(.*[[:space:]])?(main|refs/heads/main)([[:space:]]|$)|git[[:space:]]+update-ref[[:space:]]+refs/heads/main([[:space:]]|$)|git[[:space:]]+symbolic-ref[[:space:]]+HEAD([[:space:]]|$)|gh[[:space:]]+pr[[:space:]]+create([[:space:]]|$))'
}

_mbd_delegation_re() {
  printf '%s' '^[[:space:]]*\(?[[:space:]]*(cd[[:space:]]+[^[:space:]]+[[:space:]]*&&|git[[:space:]]+-C[[:space:]]+[^[:space:]]+|git[[:space:]]+--git-dir=[^[:space:]]+)'
}

_mbd_wrapper_re() {
  printf '%s' '(^|[[:space:]])(bash|sh)[[:space:]]+-c([[:space:]]|$)|(^|[[:space:]])eval([[:space:]]|$)|(^|[[:space:]])xargs[[:space:]]+([^[:space:]]+[[:space:]]+)*git([[:space:]]|$)|(^|[[:space:]])find[[:space:]].*-exec[[:space:]]+git([[:space:]]|$)'
}

_mbd_normalize() {
  printf '%s' "$1" | sed -E 's#^[[:space:]]*(\(?[[:space:]]*)?([A-Z_]+=[^[:space:]]+[[:space:]]+)+#\1#' \
                   | sed -E 's#(^|[[:space:]])(/[^[:space:]]+)?/git([[:space:]])#\1git\3#' \
                   | sed -E 's#(^|[[:space:]])git([[:space:]]+-c[[:space:]]+[^[:space:]]+)+([[:space:]])#\1git\3#'
}

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

is_forbidden_clause() {
  local clause="$1" norm
  [[ "$clause" =~ $(_mbd_wrapper_re) ]] && return 0
  norm=$(_mbd_normalize "$clause")
  [[ "$norm" =~ $(_mbd_forbidden_re) ]] || return 1
  [[ "$norm" =~ git[[:space:]]+fetch[[:space:]] ]] && _mbd_fetch_dst_remote_only "$norm" && return 1
  return 0
}

_mbd_any_clause_forbidden() {
  local clause
  while IFS= read -r clause; do
    [[ -n "$clause" ]] && is_forbidden_clause "$clause" && return 0
  done < <(split_clauses "$1")
  return 1
}

_mbd_cd_prefix_re() {
  printf '%s' '^[[:space:]]*\(?[[:space:]]*cd[[:space:]]+[^[:space:]]+[[:space:]]*&&'
}

is_forbidden_command() {
  [[ "$1" =~ $(_mbd_cd_prefix_re) ]] && return 1
  _mbd_any_clause_forbidden "$1"
}

# Test-fixture helpers (is_in_main_tree, is_in_worktree) live in
# main-branch-detect-fixtures.sh — they are used only by bats specs.

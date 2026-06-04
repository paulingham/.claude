#!/usr/bin/env bash
# Regex bank for main-branch-detect — separated to keep detect.sh ≤50 lines.
# Bash 3.2 SAFE: ERE only, no PCRE features. Each function emits ONE regex.

_mbd_forbidden_re() {
  printf '%s' '^[[:space:]]*(\(?[[:space:]]*)?(git[[:space:]]+(checkout|switch|branch[[:space:]]+-[dD]|reset[[:space:]]+--hard|merge|rebase|pull)([[:space:]]|$)|git[[:space:]]+fetch[[:space:]]+[^[:space:]]+[[:space:]]+[^[:space:]]+:[^[:space:]]+|git[[:space:]]+push[[:space:]]+[^[:space:]]+[[:space:]]+\+?[^[:space:]]*:(main|refs/heads/main)([[:space:]]|$)|git[[:space:]]+push[[:space:]].*(--delete|[[:space:]]-d)[[:space:]]+(.*[[:space:]])?(main|refs/heads/main)([[:space:]]|$)|git[[:space:]]+update-ref[[:space:]]+refs/heads/main([[:space:]]|$)|git[[:space:]]+symbolic-ref[[:space:]]+HEAD([[:space:]]|$)|gh[[:space:]]+pr[[:space:]]+create([[:space:]]|$))'
}

_mbd_delegation_re() {
  printf '%s' '^[[:space:]]*\(?[[:space:]]*(cd[[:space:]]+[^[:space:]]+[[:space:]]*&&|git[[:space:]]+-C[[:space:]]+[^[:space:]]+|git[[:space:]]+--git-dir=[^[:space:]]+)'
}

_mbd_wrapper_re() {
  printf '%s' '(^|[[:space:]])(bash|sh)[[:space:]]+-c([[:space:]]|$)|(^|[[:space:]])eval([[:space:]]|$)|(^|[[:space:]])xargs[[:space:]]+([^[:space:]]+[[:space:]]+)*git([[:space:]]|$)|(^|[[:space:]])find[[:space:]].*-exec[[:space:]]+git([[:space:]]|$)'
}

_mbd_cd_prefix_re() {
  printf '%s' '^[[:space:]]*\(?[[:space:]]*cd[[:space:]]+[^[:space:]]+[[:space:]]*&&'
}

_mbd_normalize() {
  printf '%s' "$1" | sed -E 's#^[[:space:]]*(\(?[[:space:]]*)?([A-Z_]+=[^[:space:]]+[[:space:]]+)+#\1#' \
                   | sed -E 's#(^|[[:space:]])(/[^[:space:]]+)?/git([[:space:]])#\1git\3#' \
                   | sed -E 's#(^|[[:space:]])git([[:space:]]+-c[[:space:]]+[^[:space:]]+)+([[:space:]])#\1git\3#'
}

_mbd_git_c_prefix_re() {
  printf '%s' '^[[:space:]]*(\(?[[:space:]]*)?git[[:space:]]+-C[[:space:]]+[^[:space:]]+'
}

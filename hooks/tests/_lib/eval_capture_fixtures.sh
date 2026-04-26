#!/usr/bin/env bash
# Shared fixtures + predicates for eval-capture-hook tests.

rc_eq()        { [ "$1" = "$2" ]; }
millis_under() { [ "$1" -lt "$2" ]; }
grep_file()    { grep -qF "$2" "$1" 2>/dev/null; }
contains_re()  { printf '%s' "$1" | grep -q "$2"; }
has_case_dir()     { find "$1/eval/cases/.candidates" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | grep -q .; }
no_candidate_dir() { ! has_case_dir "$1"; }
no_live_case() { ! find "$1/eval/cases" -maxdepth 1 -mindepth 1 -type d ! -name '.candidates' ! -name '_example' 2>/dev/null | grep -q .; }
has_log_file() { ls "$1/eval/runs/.capture-log/"*.log >/dev/null 2>&1; }

hook_stdin_pr_merge() {
  local pr="$1"
  printf '{"tool_name":"Bash","tool_input":{"command":"gh pr merge %s --squash"}}' "$pr"
}

make_capture_tmp() {
  local d; d="$(mktemp -d)"
  mkdir -p "$d/eval/cases/.candidates" "$d/eval/runs/.capture-log"
  printf '%s' "$d"
}

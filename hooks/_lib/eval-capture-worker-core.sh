#!/usr/bin/env bash
# Worker internals. Delegates filtering to filters.sh, logging to log.sh,
# and case authoring to the capture skill's gh-pr-to-case.sh.
source "$HERE_ECW/eval-capture-worker-filters.sh"
source "$HERE_ECW/eval-capture-worker-log.sh"

_ecw_source_lib() {
  local cap="skills/internal-eval/capture"
  # shellcheck source=/dev/null
  source "$cap/lib/oracle-match.sh"
  # shellcheck source=/dev/null
  source "$cap/lib/gh-pr-to-case.sh"
}

_ecw_skip() { ecw_log "$1" "skip" "$2"; return 0; }

_ecw_capture() {
  local pr="$1" out="eval/cases/.candidates"
  mkdir -p "$out"
  gh_pr_to_case "$pr" "$out" >/dev/null 2>&1 && ecw_log "$pr" "ok" "candidate written" \
    || ecw_log "$pr" "fail" "gh_pr_to_case returned nonzero"
}

_ecw_mark_invoked() {
  mkdir -p eval/runs/.capture-log
  : > "eval/runs/.capture-log/worker-invoked.marker"
}

eval_capture_worker() {
  local pr="$1"
  [ -z "$pr" ] && return 0
  _ecw_mark_invoked; _ecw_source_lib
  ecw_run_filters "$pr" && _ecw_capture "$pr"
}

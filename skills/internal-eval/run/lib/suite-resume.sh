#!/usr/bin/env bash
# Resume helpers: detect cases already completed and filter pending list.
# A case is "done" iff eval/runs/{run-id}/cases/{case-id}/result.json exists.

# case_already_done <run-dir> <case-id>
case_already_done() {
  [ -f "$1/cases/$2/result.json" ]
}

# filter_pending_cases <resume-flag> <run-dir> <case-id...>  -- prints pending cases, one per line.
filter_pending_cases() {
  local resume="$1"; local run_dir="$2"; shift 2
  [ "$resume" = 1 ] || { _emit_all "$@"; return; }
  _emit_pending "$run_dir" "$@"
}

_emit_all()     { for c in "$@"; do echo "$c"; done; }
_emit_pending() {
  local run_dir="$1"; shift
  for c in "$@"; do case_already_done "$run_dir" "$c" || echo "$c"; done
}

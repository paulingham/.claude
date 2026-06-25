#!/usr/bin/env bash
# Flag parser for run-suite.sh. Populates RUN_ID, SUITE, MODEL, CONCURRENCY,
# HARNESS_REF, RESUME, PREAMBLE globals. Separate from run-case's args.sh per Story 7 plan.

parse_suite_args() {
  RUN_ID=""; SUITE="default"; MODEL="opus"; CONCURRENCY=4
  HARNESS_REF=""; RESUME=0; PREAMBLE="decision-ladder"
  while [ $# -gt 0 ]; do _consume_suite_flag "$1" "${2:-}" && shift 2 || shift; done
  _validate_preamble_guard
}

_consume_suite_flag() {
  case "$1" in
    --run-id) RUN_ID="$2"; return 0 ;;
    --suite)  SUITE="$2";  return 0 ;;
    --model)  MODEL="$2";  return 0 ;;
    --concurrency) CONCURRENCY="$2"; return 0 ;;
    --harness-ref) HARNESS_REF="$2"; return 0 ;;
    --resume) RESUME=1; return 1 ;;
    --preamble) _set_preamble "$2"; return 0 ;;
  esac
  return 1
}

_set_preamble() {
  case "$1" in
    none|decision-ladder) PREAMBLE="$1" ;;
    *) echo "[run-suite] --preamble must be none|decision-ladder; got: $1" >&2; exit 2 ;;
  esac
}

# WHY: guard fires before _suite_prologue/setup_shared_harness to prevent the
# strip fn from receiving a path that doesn't exist yet (sed would silently no-op).
_validate_preamble_guard() {
  [ "$PREAMBLE" = "none" ] || return 0
  [ -n "$HARNESS_REF" ] && return 0
  echo "[run-suite] --preamble none requires --harness-ref (refuses to mutate live ~/.claude)" >&2
  exit 2
}

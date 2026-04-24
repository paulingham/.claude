#!/usr/bin/env bash
# Flag parser for run-suite.sh. Populates RUN_ID, SUITE, MODEL, CONCURRENCY,
# HARNESS_REF, RESUME globals. Separate from run-case's args.sh per Story 7 plan.

parse_suite_args() {
  RUN_ID=""; SUITE="default"; MODEL="opus"; CONCURRENCY=4; HARNESS_REF=""; RESUME=0
  while [ $# -gt 0 ]; do _consume_suite_flag "$1" "${2:-}" && shift 2 || shift; done
}

_consume_suite_flag() {
  case "$1" in
    --run-id) RUN_ID="$2"; return 0 ;;
    --suite)  SUITE="$2";  return 0 ;;
    --model)  MODEL="$2";  return 0 ;;
    --concurrency) CONCURRENCY="$2"; return 0 ;;
    --harness-ref) HARNESS_REF="$2"; return 0 ;;
    --resume) RESUME=1; return 1 ;;
  esac
  return 1
}

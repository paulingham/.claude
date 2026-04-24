#!/usr/bin/env bash
# Flag parser for run-case.sh. Populates CASE_ID, RUN_ID, HARNESS_REF, MODEL,
# TIMEOUT_SEC, DRY_RUN globals. No associative arrays (bash 3 compat).

parse_args() {
  CASE_ID=""; RUN_ID=""; HARNESS_REF=""; MODEL="opus"; TIMEOUT_SEC=1800; DRY_RUN=0
  while [ $# -gt 0 ]; do _consume_one "$1" "${2:-}" && shift 2 || shift; done
}

_consume_one() {
  case "$1" in
    --case-id) CASE_ID="$2"; return 0 ;;
    --run-id) RUN_ID="$2"; return 0 ;;
    --harness-ref) HARNESS_REF="$2"; return 0 ;;
    --model) MODEL="$2"; return 0 ;;
    --timeout) TIMEOUT_SEC="$2"; return 0 ;;
    --dry-run) DRY_RUN=1; return 1 ;;
  esac
  return 1
}

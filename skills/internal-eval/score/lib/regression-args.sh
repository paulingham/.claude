#!/usr/bin/env bash
# Flag parser for diff-vs-baseline.sh. Sets RUN_ID, BASELINE, RUNS_DIR.

parse_regression_args() {
  RUN_ID=""; BASELINE=""; RUNS_DIR="${EVAL_RUNS_DIR:-$PWD/eval/runs}"
  while [ $# -gt 0 ]; do _consume_reg "$@"; shift $CONSUMED; done
  [ -n "$RUN_ID" ] || { echo "[diff-vs-baseline] --run-id required" >&2; exit 2; }
  [ -n "$BASELINE" ] && return 0
  BASELINE="$PWD/eval/baselines/latest-opus-4-7.md"
}

_consume_reg() {
  case "$1" in
    --run-id)   RUN_ID="$2";  CONSUMED=2 ;;
    --baseline) BASELINE="$2"; CONSUMED=2 ;;
    --runs-dir) RUNS_DIR="$2"; CONSUMED=2 ;;
    *) echo "[diff-vs-baseline] unknown flag: $1" >&2; exit 2 ;;
  esac
}

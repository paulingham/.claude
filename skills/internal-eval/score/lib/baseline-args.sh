#!/usr/bin/env bash
# Flag parser for capture-baseline.sh. Sets RUN_ID, LABEL.

parse_baseline_args() {
  RUN_ID=""; LABEL=""
  while [ $# -gt 0 ]; do _consume_one "$@"; shift $CONSUMED; done
  [ -n "$RUN_ID" ] || { echo "[capture-baseline] --run-id required" >&2; exit 2; }
}

_consume_one() {
  case "$1" in
    --run-id) RUN_ID="$2"; CONSUMED=2 ;;
    --label)  LABEL="$2";  CONSUMED=2 ;;
    *) echo "[capture-baseline] unknown flag: $1" >&2; exit 2 ;;
  esac
}

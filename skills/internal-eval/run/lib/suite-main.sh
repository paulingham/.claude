#!/usr/bin/env bash
# Orchestrator for run-suite.sh: parses args, sets up harness worktree, writes
# suite.json, dispatches cases via pool, aggregates, updates suite.json.

# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/suite-cases-json.sh"
# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/suite-preamble.sh"

suite_main() {
  parse_suite_args "$@"
  local run_dir="${EVAL_RUNS_DIR:-$PWD/eval/runs}/$RUN_ID"
  mkdir -p "$run_dir/cases"
  _suite_run_phases "$run_dir"
}

_suite_run_phases() {
  _suite_prologue "$1"; _suite_dispatch_all "$1"; _suite_epilogue "$1"
}

_suite_prologue() {
  write_suite_state "$1/suite.json" "$RUN_ID" "$SUITE" "$MODEL" \
    "${HARNESS_REF:-live}" "$CONCURRENCY" running
  setup_shared_harness "$HARNESS_REF" "$1/harness-wt" >/dev/null || true
  strip_ladder_from_harness "$1/harness-wt"
}

_suite_dispatch_all() {
  local run_dir="$1"
  local cases; cases="$(_suite_pending "$run_dir")"
  trap '_suite_on_signal "$run_dir"' INT TERM
  [ -z "$cases" ] || run_pool "$CONCURRENCY" dispatch_case $cases
  trap - INT TERM
}

_suite_pending() {
  local run_dir="$1"
  local all; all="$(enumerate_cases "$SUITE" "${EVAL_CASES_DIR:-$PWD/eval/cases}")"
  filter_pending_cases "$RESUME" "$run_dir" $all | tr '\n' ' '
}

_suite_epilogue() {
  local run_dir="$1"
  aggregate_run "$run_dir" "$RUN_ID" "$SUITE" "$MODEL" "${HARNESS_REF:-live}"
  write_cases_json "$run_dir" "$RUN_ID"
  write_suite_state "$run_dir/suite.json" "$RUN_ID" "$SUITE" "$MODEL" \
    "${HARNESS_REF:-live}" "$CONCURRENCY" completed
}

_suite_on_signal() {
  local run_dir="$1"
  aggregate_run "$run_dir" "$RUN_ID" "$SUITE" "$MODEL" "${HARNESS_REF:-live}"
  write_cases_json "$run_dir" "$RUN_ID"
  write_suite_state "$run_dir/suite.json" "$RUN_ID" "$SUITE" "$MODEL" \
    "${HARNESS_REF:-live}" "$CONCURRENCY" interrupted
  exit 130
}

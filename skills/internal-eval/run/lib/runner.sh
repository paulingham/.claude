#!/usr/bin/env bash
# Main run-case driver. Composes args + isolation + harness-ref + scoring into
# a single case execution that emits result.json under EVAL_RUNS_DIR/$RUN_ID/.
# Inner /pipeline spawn is stubbed in Story 6 (Story 7 wires real dispatch).

main() {
  parse_args "$@"
  local run_dir="${EVAL_RUNS_DIR:-$PWD/eval/runs}/$RUN_ID"
  local case_dir="$run_dir/cases/$CASE_ID"
  mkdir -p "$case_dir"
  _run_case "$run_dir" "$case_dir"
}

_run_case() {
  local run_dir="$1"; local case_dir="$2"
  local shadow; shadow="$(shadow_home_path "$run_dir" "$CASE_ID")"
  local inner;  inner="$(inner_state_dir  "$run_dir" "$CASE_ID")"
  local sha;    sha="$(resolve_harness_sha "$HARNESS_REF")"
  _emit_status "$case_dir/result.json" dry_run_ok "$inner" "$sha" 0 ""
}

_emit_status() {
  local out="$1"; local status="$2"; local inner="$3"; local sha="$4"
  local duration="$5"; local reason="$6"
  write_result_json "$out" case="$CASE_ID" run="$RUN_ID" status="$status" \
    duration="$duration" cost=0 rounds=0 rework=false harness="$sha" model="$MODEL" \
    flakiness=deterministic scoring=test-passing \
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)" inner="$inner" reason="$reason"
}

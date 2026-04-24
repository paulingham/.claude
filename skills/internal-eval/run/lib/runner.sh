#!/usr/bin/env bash
# Main run-case driver. Composes args + isolation + harness-ref + scoring into
# a single case execution that emits result.json under EVAL_RUNS_DIR/$RUN_ID/.
# Inner /pipeline spawn is stubbed via EVAL_INNER_STUB (Story 6 scope);
# Story 7 wires real pipeline dispatch.

main() {
  parse_args "$@"
  local run_dir="${EVAL_RUNS_DIR:-$PWD/eval/runs}/$RUN_ID"
  local case_dir="$run_dir/cases/$CASE_ID"
  mkdir -p "$case_dir"
  _run_case "$run_dir" "$case_dir"
}

_case_ctx() {
  inner="$(inner_state_dir "$1" "$CASE_ID")"
  sha="$(resolve_harness_sha "$HARNESS_REF")"
  mode="$(resolve_scoring_mode "$CASE_ID")"
}

_run_case() {
  local run_dir="$1" case_dir="$2" inner sha mode
  _case_ctx "$run_dir"
  [ "$DRY_RUN" = 1 ] && { emit_status "$case_dir/result.json" dry_run_ok "$inner" "$sha" 0 "" 1 "$mode"; return; }
  _dispatch_inner "$case_dir/result.json" "$run_dir" "$inner" "$sha" "$mode"
}

_dispatch_inner() {
  local out="$1" run_dir="$2" inner="$3" sha="$4" mode="$5" start rc dur
  mkdir -p "$inner"; start=$(date +%s); _invoke_stub "$run_dir" "$inner"; rc=$?
  dur=$(( $(date +%s) - start ))
  emit_status "$out" "$(rc_to_status "$rc")" "$inner" "$sha" "$dur" "$(rc_reason "$rc")" 1 "$mode"
}

_invoke_stub() {
  local run_dir="$1"; local inner="$2"
  [ -n "${EVAL_INNER_STUB:-}" ] || { echo "[run-case] no EVAL_INNER_STUB; real dispatch is Story 7" >&2; return 2; }
  run_with_timeout "$TIMEOUT_SEC" "$EVAL_INNER_STUB" "$run_dir" "$inner"
}

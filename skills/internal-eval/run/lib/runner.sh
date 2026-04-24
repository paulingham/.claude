#!/usr/bin/env bash
# Main run-case driver. Composes args + isolation + harness-ref + scoring into
# a single case execution that emits result.json under EVAL_RUNS_DIR/$RUN_ID/.
# Inner /pipeline defaults to real `claude`; EVAL_INNER_STUB / EVAL_CLAUDE_BIN
# are test seams.

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
  mkdir -p "$inner"; start=$(date +%s); _run_inner "$run_dir" "$inner" "$sha"; rc=$?
  dur=$(( $(date +%s) - start ))
  emit_status "$out" "$(rc_to_status "$rc")" "$inner" "$sha" "$dur" "$(rc_reason "$rc")" 1 "$mode"
}

_invoke_stub() {
  run_with_timeout "$TIMEOUT_SEC" "$EVAL_INNER_STUB" "$1" "$2"
}

# _invoke_real <run_dir> <inner> — real `claude -p /pipeline`; rc 2 on infra.
_invoke_real() {
  local bin="${EVAL_CLAUDE_BIN:-claude}" task
  task="${EVAL_CASES_DIR:-$PWD/eval/cases}/$CASE_ID/task.md"
  _real_preflight "$bin" "$task" || return 2
  run_with_timeout "$TIMEOUT_SEC" "$bin" -p "/pipeline $(cat "$task")" >"$2/pipeline.stdout" 2>"$2/pipeline.stderr"
}

_real_preflight() {
  command -v "$1" >/dev/null 2>&1 || { echo "[run-case] claude bin not found: $1" >&2; return 1; }
  [ -f "$2" ] || { echo "[run-case] missing task.md: $2" >&2; return 1; }
}

#!/usr/bin/env bash
# Tests that emit_status threads per-case scoring_mode into result.json
# rather than hardcoding "test-passing".

_emit_with_mode() {
  local run="$1" out="$2" mode="$3"
  source "$run/lib/status.sh"; source "$run/lib/result-emit.sh"
  CASE_ID=c1 RUN_ID=r1 MODEL=opus \
    emit_status "$out" passed inner-dir sha123 5 "" 1 "$mode"
}

_mode_written() {
  local run="$1" mode="$2" tmp; tmp="$(mktemp -d)"
  _emit_with_mode "$run" "$tmp/r.json" "$mode"
  [ "$(jq -r .scoring_mode "$tmp/r.json")" = "$mode" ]; local rc=$?
  rm -rf "$tmp"; return "$rc"
}

check_emit_status_scoring_modes() {
  local run="$1"
  assert "emit_status: scoring_mode=exact written"       _mode_written "$run" exact
  assert "emit_status: scoring_mode=normalized written"  _mode_written "$run" normalized
  assert "emit_status: scoring_mode=test-passing written" _mode_written "$run" test-passing
}

_stage_case_meta() {
  local cases="$1" id="$2" mode="$3"; mkdir -p "$cases/$id"
  printf '{"case_id":"%s","scoring_mode":"%s","timeout_minutes":30}\n' \
    "$id" "$mode" > "$cases/$id/metadata.json"
}

_dry_run_result_mode() {
  local run="$1" mode="$2" tmp cases
  tmp="$(mktemp -d)"; cases="$tmp/cases"; _stage_case_meta "$cases" c42 "$mode"
  EVAL_RUNS_DIR="$tmp/runs" EVAL_CASES_DIR="$cases" \
    bash "$run/run-case.sh" --case-id c42 --run-id rm --dry-run >/dev/null
  jq -r .scoring_mode "$tmp/runs/rm/cases/c42/result.json"; rm -rf "$tmp"
}

check_runner_threads_scoring_mode() {
  local run="$1"
  assert "runner: metadata scoring_mode=exact → result.scoring_mode=exact" \
    _eq "$(_dry_run_result_mode "$run" exact)" "exact"
  assert "runner: metadata scoring_mode=normalized → result.scoring_mode=normalized" \
    _eq "$(_dry_run_result_mode "$run" normalized)" "normalized"
}

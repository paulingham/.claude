#!/usr/bin/env bash
# Test helpers for Story 6 run-case.sh. Each check function performs a
# single focused assertion; keeps the test runner thin.

REQUIRED_RESULT_KEYS="case_id run_id status duration_sec cost_usd review_rounds rework harness_ref model flakiness_tier scoring_mode timestamp inner_pipeline_state failure_reason"

check_result_writer() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/status.sh"
  local tmp; tmp="$(mktemp -d)"
  write_result_json "$tmp/result.json" case=c1 run=r1 status=passed \
    duration=12.5 cost=0.0 rounds=0 rework=false harness=live model=opus \
    flakiness=deterministic scoring=test-passing ts=2026-04-24T00:00:00Z \
    inner="$tmp/inner" reason=""
  assert "write_result_json: file exists"            is_file "$tmp/result.json"
  assert "write_result_json: valid JSON"             json_valid "$tmp/result.json"
  for k in $REQUIRED_RESULT_KEYS; do
    assert "write_result_json: has key $k"           json_has "$tmp/result.json" "$k"
  done
  rm -rf "$tmp"
}

check_isolation_paths() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/isolation.sh"
  assert "shadow_home_path: under run-dir/home" _eq "$(shadow_home_path /tmp/eval-r1 c5)" "/tmp/eval-r1/home/c5"
  assert "inner_state_dir: under run-dir/inner" _eq "$(inner_state_dir /tmp/eval-r1 c5)" "/tmp/eval-r1/inner/c5"
}

check_isolation_env() {
  local run="$1"; local tmp; tmp="$(mktemp -d)"
  [ -f "$run/lib/isolation.sh" ] || { assert "isolation.sh exists" false; return; }
  # shellcheck disable=SC1091
  source "$run/lib/isolation.sh"
  export_isolation_env r42 c7 "$tmp/home"
  assert "isolation: CLAUDE_PIPELINE_TASK_ID" _eq "${CLAUDE_PIPELINE_TASK_ID:-}" "eval-r42-c7"
  assert "isolation: CLAUDE_PIPELINE_BYPASS=1" _eq "${CLAUDE_PIPELINE_BYPASS:-}" "1"
  assert "isolation: CLAUDE_DISABLE_AUTO_LEARN=1" _eq "${CLAUDE_DISABLE_AUTO_LEARN:-}" "1"
  assert "isolation: CLAUDE_PROJECT_HASH" _eq "${CLAUDE_PROJECT_HASH:-}" "eval-r42-c7"
  assert "isolation: EVAL_RUN_ID" _eq "${EVAL_RUN_ID:-}" "r42"
  assert "isolation: EVAL_CASE_ID" _eq "${EVAL_CASE_ID:-}" "c7"
  assert "isolation: HOME is shadow" _eq "${HOME:-}" "$tmp/home"
  rm -rf "$tmp"
}

_eq() { [ "$1" = "$2" ]; }

check_status_enum() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/status.sh"
  assert "status.sh: passed is valid"        is_valid_status "passed"
  assert "status.sh: failed_diff is valid"   is_valid_status "failed_diff"
  assert "status.sh: failed_build is valid"  is_valid_status "failed_build"
  assert "status.sh: failed_timeout is valid" is_valid_status "failed_timeout"
  assert "status.sh: failed_infra is valid"  is_valid_status "failed_infra"
  assert "status.sh: dry_run_ok is valid"    is_valid_status "dry_run_ok"
  assert_not "status.sh: bogus is invalid"   is_valid_status "bogus"
}

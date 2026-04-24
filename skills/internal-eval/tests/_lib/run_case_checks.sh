#!/usr/bin/env bash
# Test helpers for Story 6 run-case.sh. Each check function performs a
# single focused assertion; keeps the test runner thin.

REQUIRED_RESULT_KEYS="case_id run_id status duration_sec cost_usd review_rounds rework harness_ref model flakiness_tier scoring_mode timestamp inner_pipeline_state failure_reason"
FIXTURE=""

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

check_scoring_stub() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/scoring.sh"
  assert "scoring: all gates green → passed" \
    _eq "$(score_case APPROVE APPROVE VERIFIED COVERED APPROVED)" "passed"
  assert "scoring: review CHANGES_REQUESTED → failed_diff" \
    _eq "$(score_case CHANGES_REQUESTED APPROVE VERIFIED COVERED APPROVED)" "failed_diff"
  assert "scoring: verify UNVERIFIED → failed_diff" \
    _eq "$(score_case APPROVE APPROVE UNVERIFIED COVERED APPROVED)" "failed_diff"
  assert "scoring: accept REJECTED → failed_diff" \
    _eq "$(score_case APPROVE APPROVE VERIFIED COVERED REJECTED)" "failed_diff"
}

check_harness_ref_failure() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/harness-ref.sh"
  local tmp; tmp="$(mktemp -d)"; mkdir -p "$tmp/norepo"
  assert_not "harness-ref: bad sha → non-zero exit" \
    _call_resolve_with_bad_repo "$tmp/norepo" "$tmp/wt"
  rm -rf "$tmp"
}

_call_resolve_with_bad_repo() {
  CLAUDE_HARNESS_REPO="$1" resolve_harness_root "deadbeef" "$2" >/dev/null
}

check_harness_ref_pinned() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/harness-ref.sh"
  FIXTURE="$(mktemp -d)"
  local sha; sha="$(_setup_harness_fixture "$FIXTURE")"
  local wt="$FIXTURE/wt"
  local root; root="$(CLAUDE_HARNESS_REPO="$FIXTURE/repo" resolve_harness_root "$sha" "$wt")"
  assert "harness-ref: pinned root = wt path" _eq "$root" "$wt"
  assert "harness-ref: pinned tree has marker v1" is_file "$root/marker-v1"
  assert_not "harness-ref: pinned tree lacks v2" is_file "$root/marker-v2"
  rm -rf "$FIXTURE"
}

_setup_harness_fixture() {
  local fx="$1"; mkdir -p "$fx/repo"
  (cd "$fx/repo" && git init -q && git config user.email t@t && git config user.name t \
    && touch marker-v1 && git add marker-v1 && git commit -q -m v1 \
    && git rev-parse HEAD > "$fx/sha1" \
    && touch marker-v2 && git add marker-v2 && git commit -q -m v2) >&2
  cat "$fx/sha1"
}

check_harness_ref() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/harness-ref.sh"
  assert "harness-ref: live default sha" _eq "$(resolve_harness_sha "")" "live"
  assert "harness-ref: live default root" _eq "$(resolve_harness_root "" /tmp/nope)" "$HOME"
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

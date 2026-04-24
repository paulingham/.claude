#!/usr/bin/env bash
# Worker-level checks for eval-capture tests. Args: hooks_dir, repo_root.
source "$(dirname "${BASH_SOURCE[0]}")/eval_capture_helpers.sh"

check_worker_date_filter() {
  local tmp; tmp="$(make_capture_tmp)"; _prep_worker_env "$tmp" "$2"
  _write_fixture_old_merge "$tmp/fixtures" 77
  _run_worker "$1" "$tmp" "$tmp/fixtures" 77 "oldpr"
  assert "worker: old-merge PR skipped" no_candidate_dir "$tmp"; rm -rf "$tmp"
}

check_worker_oracle_filter() {
  local tmp; tmp="$(make_capture_tmp)"; _prep_worker_env "$tmp" "$2"
  _run_worker "$1" "$tmp" "$tmp/fixtures" 200 "docs_pr"
  assert "worker: no-oracle PR skipped" no_candidate_dir "$tmp"; rm -rf "$tmp"
}

check_worker_happy_path() {
  local tmp; tmp="$(make_capture_tmp)"; _prep_worker_env "$tmp" "$2"
  _run_worker "$1" "$tmp" "$tmp/fixtures" 100 "test_pr"
  assert "worker: happy path writes to .candidates/" has_case_dir "$tmp"; rm -rf "$tmp"
}

check_worker_never_promotes() {
  local tmp; tmp="$(make_capture_tmp)"; _prep_worker_env "$tmp" "$2"
  _run_worker "$1" "$tmp" "$tmp/fixtures" 100 "test_pr"
  assert "worker: never writes to eval/cases/ directly" no_live_case "$tmp"; rm -rf "$tmp"
}

check_worker_capture_log() {
  local tmp; tmp="$(make_capture_tmp)"; _prep_worker_env "$tmp" "$2"
  _run_worker "$1" "$tmp" "$tmp/fixtures" 100 "test_pr"
  assert "worker: capture-log file created on success" has_log_file "$tmp"; rm -rf "$tmp"
}

check_worker_capture_log_on_skip() {
  local tmp; tmp="$(make_capture_tmp)"; _prep_worker_env "$tmp" "$2"
  _run_worker "$1" "$tmp" "$tmp/fixtures" 200 "docs_pr"
  assert "worker: capture-log file created on skip" has_log_file "$tmp"; rm -rf "$tmp"
}

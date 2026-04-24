#!/usr/bin/env bash
# Scenario runners: banner + oracle matching. Promote/pr_to_case live in sibling files.
source "$(dirname "${BASH_SOURCE[0]}")/backfill_promote.sh"
source "$(dirname "${BASH_SOURCE[0]}")/backfill_pr_to_case.sh"

_run_backfill() {
  local tmp="$1" fix="$2" cap="$3" limit="${4:-5}"
  (cd "$tmp" && PATH="$tmp/bin:$PATH" CLAUDE_EVAL_FIX_DIR="$tmp/fixtures" \
     CLAUDE_EVAL_FIXTURE="$fix" bash "$cap/backfill.sh" --limit "$limit" >/dev/null 2>&1) || true
}

run_banner_missing() {
  local cap="$1" tmp="$2" out rc
  out="$(cd "$tmp" && bash "$cap/backfill.sh" --limit 1 2>&1)"; rc=$?
  assert "banner: missing marker → rc=1"          rc_eq "$rc" "1"
  assert "banner: missing marker → prints banner" contains "$out" "privacy"
}

run_banner_present() {
  local cap="$1" tmp="$2" out
  touch "$tmp/eval/.privacy-acked"
  out="$(cd "$tmp" && PATH="$tmp/bin:$PATH" CLAUDE_EVAL_FIXTURE=empty bash "$cap/backfill.sh" --limit 0 2>&1)"
  assert "banner: marker present → no 'create marker' msg" not_contains "$out" "create.*marker"
}

run_match_positive() {
  local cap="$1" tests="$2" tmp="$3"
  write_gh_shim "$tmp" "$tests"; touch "$tmp/eval/.privacy-acked"
  _run_backfill "$tmp" "test_pr" "$cap" 5
  assert "oracle: test PR captured" has_candidate_dir "$tmp"
}

run_match_negative() {
  local cap="$1" tests="$2" tmp="$3"
  write_gh_shim "$tmp" "$tests"; touch "$tmp/eval/.privacy-acked"
  _run_backfill "$tmp" "docs_pr" "$cap" 5
  assert "oracle: docs PR excluded" has_exclusion_report "$tmp"
}

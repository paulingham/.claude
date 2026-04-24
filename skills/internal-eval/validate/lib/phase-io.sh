#!/usr/bin/env bash
# Skill-subprocess invocations for the validation sequence: run-suite,
# capture-baseline, diff-vs-baseline. Each wrapper pins the eval env vars
# that point at the per-test temp dirs instead of the live $PWD/eval.

_io_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SKILL_ROOT="$(cd "$_io_dir/../.." && pwd)"

run_suite_in() {
  local tmp="$1"; local run_id="$2"
  EVAL_CASES_DIR="$tmp/cases" EVAL_RUNS_DIR="$tmp/runs" \
    EVAL_INNER_STUB="$_io_dir/stub-manifest.sh" \
    VALIDATE_STUB_MANIFEST="$tmp/manifest.json" \
    bash "$_SKILL_ROOT/run/run-suite.sh" --run-id "$run_id" --concurrency 2 >/dev/null
}

run_capture_baseline() {
  local tmp="$1"; local run_id="$2"
  EVAL_RUNS_DIR="$tmp/runs" EVAL_BASELINES_DIR="$tmp/baselines" \
    bash "$_SKILL_ROOT/score/capture-baseline.sh" --run-id "$run_id" >/dev/null
}

run_diff_vs_baseline() {
  local tmp="$1"; local run_id="$2"
  local baseline; baseline="$(_resolve_latest_baseline "$tmp/baselines")"
  EVAL_RUNS_DIR="$tmp/runs" \
    bash "$_SKILL_ROOT/score/diff-vs-baseline.sh" \
      --run-id "$run_id" --baseline "$baseline" --runs-dir "$tmp/runs" >/dev/null
}

_resolve_latest_baseline() {
  find "$1" -maxdepth 1 -name 'latest-*.md' | head -1
}

#!/usr/bin/env bash
# Phase runners for the Story 11 validation sequence. Phase A baselines
# an all-pass run; Phase B injects ≥2 deterministic failures via the stub
# manifest; Phase C diffs and expects EVAL_FAILED; Phase D restores the
# manifest; Phase E diffs again and expects EVAL_PASSED.

_pr_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_pr_dir/seed.sh"
# shellcheck disable=SC1091
source "$_pr_dir/phase-io.sh"
# shellcheck disable=SC1091
source "$_pr_dir/phase-mutate.sh"

phase_a() {
  local tmp="$1"
  _phase_prepare "$tmp"; echo '{}' > "$tmp/manifest.json"
  run_suite_in "$tmp" "baseline"
  run_capture_baseline "$tmp" "baseline"
}

phase_b() {
  local tmp="$1"
  jq -n '{"validate-a":"fail","validate-b":"fail"}' > "$tmp/manifest.json"
  run_suite_in "$tmp" "inject"
  rewrite_failed_as_diff "$tmp/runs/inject"
  reaggregate "$tmp/runs/inject" inject
}

phase_c() { run_diff_vs_baseline "$1" "inject" || true; }

phase_d() {
  local tmp="$1"
  echo '{}' > "$tmp/manifest.json"
  run_suite_in "$tmp" "restore"
}

phase_e() { run_diff_vs_baseline "$1" "restore" || true; }

_phase_prepare() {
  local tmp="$1"
  seed_cases "$tmp/cases"
  mkdir -p "$tmp/runs" "$tmp/baselines"
}

#!/usr/bin/env bash
# Sequence-level assertions. Each run_phase_*_asserts composes the low-level
# checks from assertions.sh into the full Story 11 contract. Any failure
# causes the calling script to exit non-zero via set -e.

set -e

run_phase_a_asserts() {
  local tmp="$1"
  assert_pass_rate_equals "$tmp/runs/baseline/aggregate.json" "1"
  [ -L "$tmp/baselines/latest-opus.md" ] \
    || { echo "[assert] phase-A: latest-opus.md symlink missing" >&2; return 1; }
}

run_phase_b_asserts() {
  local tmp="$1"
  local n; n="$(jq -r .failed_diff "$tmp/runs/inject/aggregate.json")"
  [ "$n" -ge 2 ] \
    || { echo "[assert] phase-B: failed_diff=$n (want ≥2)" >&2; return 1; }
}

run_phase_c_asserts() {
  local tmp="$1"
  assert_verdict "$tmp/runs/inject/regression.json" "EVAL_FAILED"
  assert_regression_count_ge "$tmp/runs/inject/regression.json" 2
  assert_case_in_regressions "$tmp/runs/inject/regression.json" "validate-a"
  assert_case_in_regressions "$tmp/runs/inject/regression.json" "validate-b"
}

run_phase_d_asserts() {
  local root="$1"; local sha_before="$2"
  local sha_after; sha_after="$(shasum "$root/agents/code-reviewer.md" | awk '{print $1}')"
  [ "$sha_before" = "$sha_after" ] \
    || { echo "[assert] phase-D: agents/code-reviewer.md SHA changed" >&2; return 1; }
}

run_phase_e_asserts() {
  local r="$1/runs/restore/regression.json"
  assert_verdict "$r" "EVAL_PASSED"
  local rc; rc="$(jq -r .regression_count "$r")"
  [ "$rc" = "0" ] || { echo "[assert] phase-E: regression_count=$rc (want 0)" >&2; return 1; }
}

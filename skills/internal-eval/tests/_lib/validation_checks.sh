#!/usr/bin/env bash
# Test helpers for Story 11 validation sequence. Each check is single-purpose.

_vc_eq() { [ "$1" = "$2" ]; }
_vc_ge() { [ "$1" -ge "$2" ]; }

check_stub_reads_manifest_pass() {
  local val="$1"
  local tmp; tmp="$(mktemp -d)"
  echo '{"case-a":"pass"}' > "$tmp/m.json"
  VALIDATE_STUB_MANIFEST="$tmp/m.json" \
    bash "$val/lib/stub-manifest.sh" "$tmp" "$tmp/inner/case-a"; local rc=$?
  assert "stub: pass case → rc=0" _vc_eq "$rc" "0"
  rm -rf "$tmp"
}

check_stub_reads_manifest_fail() {
  local val="$1"
  local tmp; tmp="$(mktemp -d)"
  echo '{"case-b":"fail"}' > "$tmp/m.json"
  VALIDATE_STUB_MANIFEST="$tmp/m.json" \
    bash "$val/lib/stub-manifest.sh" "$tmp" "$tmp/inner/case-b"; local rc=$?
  assert "stub: fail case → rc=1" _vc_eq "$rc" "1"
  rm -rf "$tmp"
}

check_stub_default_pass() {
  local val="$1"
  local tmp; tmp="$(mktemp -d)"
  echo '{}' > "$tmp/m.json"
  VALIDATE_STUB_MANIFEST="$tmp/m.json" \
    bash "$val/lib/stub-manifest.sh" "$tmp" "$tmp/inner/unknown-c"; local rc=$?
  assert "stub: unlisted case defaults to pass → rc=0" _vc_eq "$rc" "0"
  rm -rf "$tmp"
}

check_seed_creates_three_cases() {
  local val="$1"
  local tmp; tmp="$(mktemp -d)"
  # shellcheck disable=SC1091
  source "$val/lib/seed.sh"
  seed_cases "$tmp/cases"
  local n; n="$(find "$tmp/cases" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
  assert "seed: creates ≥3 case dirs" _vc_ge "$n" "3"
  assert "seed: each case has metadata.json" _vc_eq \
    "$(find "$tmp/cases" -name metadata.json | wc -l | tr -d ' ')" "$n"
  rm -rf "$tmp"
}

check_assert_pass_rate_equals() {
  local val="$1"
  # shellcheck disable=SC1091
  source "$val/lib/assertions.sh"
  local tmp; tmp="$(mktemp -d)"
  echo '{"pass_rate":1.00}' > "$tmp/agg.json"
  assert_pass_rate_equals "$tmp/agg.json" "1.00"; local rc=$?
  assert "assertions: pass_rate matches → rc=0" _vc_eq "$rc" "0"
  echo '{"pass_rate":0.33}' > "$tmp/agg.json"
  assert_pass_rate_equals "$tmp/agg.json" "1.00" 2>/dev/null; local rc2=$?
  assert "assertions: pass_rate mismatch → rc≠0" _vc_eq "$rc2" "1"
  rm -rf "$tmp"
}

check_assert_verdict() {
  local val="$1"
  # shellcheck disable=SC1091
  source "$val/lib/assertions.sh"
  local tmp; tmp="$(mktemp -d)"
  echo '{"verdict":"EVAL_FAILED"}' > "$tmp/r.json"
  assert_verdict "$tmp/r.json" "EVAL_FAILED"; local rc=$?
  assert "assertions: verdict match → rc=0" _vc_eq "$rc" "0"
  assert_verdict "$tmp/r.json" "EVAL_PASSED" 2>/dev/null; local rc2=$?
  assert "assertions: verdict mismatch → rc≠0" _vc_eq "$rc2" "1"
  rm -rf "$tmp"
}

check_assert_regression_count_ge() {
  local val="$1"
  # shellcheck disable=SC1091
  source "$val/lib/assertions.sh"
  local tmp; tmp="$(mktemp -d)"
  echo '{"regression_count":3}' > "$tmp/r.json"
  assert_regression_count_ge "$tmp/r.json" 2; local rc=$?
  assert "assertions: regression_count≥2 when 3 → rc=0" _vc_eq "$rc" "0"
  echo '{"regression_count":0}' > "$tmp/r.json"
  assert_regression_count_ge "$tmp/r.json" 2 2>/dev/null; local rc2=$?
  assert "assertions: regression_count<2 → rc≠0" _vc_eq "$rc2" "1"
  rm -rf "$tmp"
}

check_rewrite_failed_to_diff() {
  local val="$1"
  # shellcheck disable=SC1091
  source "$val/lib/phase-runners.sh"
  local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/cases/c1" "$tmp/cases/c2" "$tmp/cases/c3"
  echo '{"case_id":"c1","status":"failed_build"}' > "$tmp/cases/c1/result.json"
  echo '{"case_id":"c2","status":"failed_build"}' > "$tmp/cases/c2/result.json"
  echo '{"case_id":"c3","status":"passed"}'      > "$tmp/cases/c3/result.json"
  rewrite_failed_as_diff "$tmp"
  assert "rewrite: c1 now failed_diff" _vc_eq \
    "$(jq -r .status "$tmp/cases/c1/result.json")" "failed_diff"
  assert "rewrite: c2 now failed_diff" _vc_eq \
    "$(jq -r .status "$tmp/cases/c2/result.json")" "failed_diff"
  assert "rewrite: c3 still passed"    _vc_eq \
    "$(jq -r .status "$tmp/cases/c3/result.json")" "passed"
  rm -rf "$tmp"
}

check_phase_a_produces_baseline() {
  local val="$1"; local root="$2"
  # shellcheck disable=SC1091
  source "$val/lib/phase-runners.sh"
  local tmp; tmp="$(mktemp -d)"
  phase_a "$tmp" >/dev/null 2>&1
  assert "phase-A: baseline file created"       \
    test -f "$tmp/baselines/latest-opus.md" -o -L "$tmp/baselines/latest-opus.md"
  assert "phase-A: baseline aggregate pass_rate=1" _vc_eq \
    "$(jq -r .pass_rate "$tmp/runs/baseline/aggregate.json")" "1"
  rm -rf "$tmp"
}

check_phase_b_injects_regressions() {
  local val="$1"; local root="$2"
  # shellcheck disable=SC1091
  source "$val/lib/phase-runners.sh"
  local tmp; tmp="$(mktemp -d)"
  phase_a "$tmp" >/dev/null 2>&1
  phase_b "$tmp" >/dev/null 2>&1
  local n_fail; n_fail="$(jq -r .failed_diff "$tmp/runs/inject/aggregate.json")"
  assert "phase-B: ≥2 failed_diff statuses" _vc_ge "$n_fail" "2"
  rm -rf "$tmp"
}

check_phase_c_flags_regressions() {
  local val="$1"; local root="$2"
  # shellcheck disable=SC1091
  source "$val/lib/phase-runners.sh"
  local tmp; tmp="$(mktemp -d)"
  phase_a "$tmp" >/dev/null 2>&1
  phase_b "$tmp" >/dev/null 2>&1
  phase_c "$tmp" >/dev/null 2>&1
  assert "phase-C: regression.json verdict EVAL_FAILED" _vc_eq \
    "$(jq -r .verdict "$tmp/runs/inject/regression.json")" "EVAL_FAILED"
  local rc; rc="$(jq -r .regression_count "$tmp/runs/inject/regression.json")"
  assert "phase-C: regression_count ≥2" _vc_ge "$rc" "2"
  rm -rf "$tmp"
}

check_phase_d_restores_cleanly() {
  local val="$1"; local root="$2"
  # shellcheck disable=SC1091
  source "$val/lib/phase-runners.sh"
  local tmp; tmp="$(mktemp -d)"
  phase_a "$tmp" >/dev/null 2>&1
  local sha_before="$(shasum "$root/agents/code-reviewer.md" | awk '{print $1}')"
  phase_b "$tmp" >/dev/null 2>&1
  phase_d "$tmp" >/dev/null 2>&1
  local sha_after="$(shasum "$root/agents/code-reviewer.md" | awk '{print $1}')"
  assert "phase-D: agents/code-reviewer.md SHA unchanged across sequence" \
    _vc_eq "$sha_before" "$sha_after"
  rm -rf "$tmp"
}

check_regression_cases_named() {
  local val="$1"
  # shellcheck disable=SC1091
  source "$val/lib/phase-runners.sh"
  # shellcheck disable=SC1091
  source "$val/lib/assertions.sh"
  local tmp; tmp="$(mktemp -d)"
  phase_a "$tmp" >/dev/null 2>&1
  phase_b "$tmp" >/dev/null 2>&1
  phase_c "$tmp" >/dev/null 2>&1
  assert "regressions: validate-a flagged" \
    assert_case_in_regressions "$tmp/runs/inject/regression.json" "validate-a"
  assert "regressions: validate-b flagged" \
    assert_case_in_regressions "$tmp/runs/inject/regression.json" "validate-b"
  rm -rf "$tmp"
}

check_full_sequence_exit_zero() {
  local val="$1"
  local tmp; tmp="$(mktemp -d)"
  bash "$val/run-validation-sequence.sh" "$tmp" >/dev/null 2>&1; local rc=$?
  assert "full-sequence: exits 0 on clean run" _vc_eq "$rc" "0"
  rm -rf "$tmp"
}

check_full_sequence_detects_missed_regression() {
  local val="$1"
  local tmp; tmp="$(mktemp -d)"
  # Force phase-C to NOT see a regression by breaking the injection step:
  # override phase_b via a wrapper script that leaves the stub manifest empty.
  VALIDATE_FORCE_CLEAN_INJECT=1 \
    bash "$val/run-validation-sequence.sh" "$tmp" >/dev/null 2>&1; local rc=$?
  assert "full-sequence: exits non-zero when injected regression not detected" \
    _vc_ne "$rc" "0"
  rm -rf "$tmp"
}

_vc_ne() { [ "$1" != "$2" ]; }

check_phase_e_clean_verdict() {
  local val="$1"; local root="$2"
  # shellcheck disable=SC1091
  source "$val/lib/phase-runners.sh"
  local tmp; tmp="$(mktemp -d)"
  phase_a "$tmp" >/dev/null 2>&1
  phase_b "$tmp" >/dev/null 2>&1
  phase_c "$tmp" >/dev/null 2>&1
  phase_d "$tmp" >/dev/null 2>&1
  phase_e "$tmp" >/dev/null 2>&1
  assert "phase-E: regression.json verdict EVAL_PASSED" _vc_eq \
    "$(jq -r .verdict "$tmp/runs/restore/regression.json")" "EVAL_PASSED"
  assert "phase-E: regression_count=0" _vc_eq \
    "$(jq -r .regression_count "$tmp/runs/restore/regression.json")" "0"
  rm -rf "$tmp"
}

check_seed_deterministic_tier() {
  local val="$1"
  local tmp; tmp="$(mktemp -d)"
  # shellcheck disable=SC1091
  source "$val/lib/seed.sh"
  seed_cases "$tmp/cases"
  local quarantined; quarantined="$(grep -l quarantined "$tmp/cases"/*/metadata.json 2>/dev/null | wc -l | tr -d ' ')"
  assert "seed: no quarantined cases (intersection math needs deterministic)" \
    _vc_eq "$quarantined" "0"
  rm -rf "$tmp"
}

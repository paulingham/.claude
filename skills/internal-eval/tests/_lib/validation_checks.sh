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

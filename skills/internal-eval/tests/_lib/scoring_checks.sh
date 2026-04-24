#!/usr/bin/env bash
# Story 8 scoring tests: oracle modes + flakiness retry + attempts metadata.

_eq() { [ "$1" = "$2" ]; }

check_exact_mode_pass() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/scoring-modes/exact.sh"
  local tmp; tmp="$(mktemp -d)"
  printf 'diff --git a/x\n+foo\n' > "$tmp/gold.patch"
  printf 'diff --git a/x\n+foo\n' > "$tmp/cand.patch"
  assert "exact: byte-equal diffs pass" score_exact "$tmp/gold.patch" "$tmp/cand.patch"
  rm -rf "$tmp"
}

check_exact_mode_fail() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/scoring-modes/exact.sh"
  local tmp; tmp="$(mktemp -d)"
  printf 'diff --git a/x\n+foo\n' > "$tmp/gold.patch"
  printf 'diff --git a/x\n+bar\n' > "$tmp/cand.patch"
  assert_not "exact: differing diffs fail" score_exact "$tmp/gold.patch" "$tmp/cand.patch"
  rm -rf "$tmp"
}

check_score_dispatch_gate_fail() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/scoring.sh"
  local status
  status="$(score_case_full CHANGES_REQUESTED APPROVE VERIFIED COVERED APPROVED exact :: ::)"
  assert "dispatch: gate fail → failed_diff (mode never consulted)" _eq "$status" failed_diff
}

check_score_dispatch_exact_pass() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/scoring.sh"
  local tmp; tmp="$(mktemp -d)"
  printf 'x\n' > "$tmp/g"; printf 'x\n' > "$tmp/c"
  local status
  status="$(score_case_full APPROVE APPROVE VERIFIED COVERED APPROVED exact "$tmp/g" "$tmp/c")"
  assert "dispatch: gates green + exact match → passed" _eq "$status" passed
  rm -rf "$tmp"
}

check_score_dispatch_exact_fail() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/scoring.sh"
  local tmp; tmp="$(mktemp -d)"
  printf 'x\n' > "$tmp/g"; printf 'y\n' > "$tmp/c"
  local status
  status="$(score_case_full APPROVE APPROVE VERIFIED COVERED APPROVED exact "$tmp/g" "$tmp/c")"
  assert "dispatch: gates green + exact mismatch → failed_diff" _eq "$status" failed_diff
  rm -rf "$tmp"
}

check_test_passing_mode() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/scoring-modes/test-passing.sh"
  local tmp; tmp="$(mktemp -d)"
  local pass="$tmp/pass.sh"; printf '#!/usr/bin/env bash\nexit 0\n' > "$pass"; chmod +x "$pass"
  local fail="$tmp/fail.sh"; printf '#!/usr/bin/env bash\nexit 1\n' > "$fail"; chmod +x "$fail"
  assert "test-passing: passing oracle passes"       score_test_passing "$pass"
  assert_not "test-passing: failing oracle fails"    score_test_passing "$fail"
  rm -rf "$tmp"
}

check_normalized_mode() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/scoring-modes/normalized.sh"
  local tmp; tmp="$(mktemp -d)"
  printf '+foo\n+bar\n' > "$tmp/a"
  printf '+foo\n\n+bar   \n' > "$tmp/b"
  printf '+bar\n+foo\n' > "$tmp/c"
  assert "normalized: whitespace-only diff matches" score_normalized "$tmp/a" "$tmp/b"
  assert_not "normalized: semantic diff still fails" score_normalized "$tmp/a" "$tmp/c"
  rm -rf "$tmp"
}

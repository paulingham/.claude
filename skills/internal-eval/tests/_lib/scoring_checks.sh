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

check_retry_deterministic_no_retry() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/retry.sh"
  local calls=0; _incr() { calls=$((calls+1)); return 1; }
  score_with_retry deterministic _incr >/dev/null || true
  assert "retry: deterministic → 1 attempt only" _eq "$calls" 1
}

check_retry_2x_passes_second() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/retry.sh"
  local calls=0
  _fail_then_pass() { calls=$((calls+1)); [ "$calls" -ge 2 ]; }
  local out; out="$(score_with_retry retriable-2x _fail_then_pass 2>&1)"
  local rc=$?
  assert "retry: 2x passes on attempt 2"  _eq "$rc" 0
  assert "retry: emitted attempts=2"      _eq "$out" "attempts=2"
}

check_retry_2x_all_fail() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/retry.sh"
  local tmp; tmp="$(mktemp -d)"; : > "$tmp/calls"
  _always_fail() { echo x >> "$tmp/calls"; return 1; }
  local out; out="$(score_with_retry retriable-2x _always_fail 2>&1)"
  local rc=$?
  assert_not "retry: 2x returns non-zero after budget" [ "$rc" = 0 ]
  assert "retry: 2x capped at 2 attempts" _eq "$(wc -l < "$tmp/calls" | tr -d ' ')" 2
  assert "retry: emitted attempts=2"      _eq "$out" "attempts=2"
  rm -rf "$tmp"
}

check_retry_quarantined_runs_once() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/retry.sh"
  local calls=0; _fail() { calls=$((calls+1)); return 1; }
  score_with_retry quarantined _fail >/dev/null || true
  assert "retry: quarantined → 1 attempt (no retry)" _eq "$calls" 1
}

check_result_json_has_attempts() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/status.sh"
  local tmp; tmp="$(mktemp -d)"
  write_result_json "$tmp/r.json" case=c1 run=r1 status=passed duration=1 cost=0 \
    rounds=0 rework=false harness=abc model=opus flakiness=retriable-2x \
    scoring=exact ts="2026-04-24T00:00:00Z" inner="" reason="" attempts=2
  assert "result.json: attempts field emitted" _eq "$(jq -r .attempts "$tmp/r.json")" 2
  assert "result.json: flakiness_tier preserved" \
    _eq "$(jq -r .flakiness_tier "$tmp/r.json")" "retriable-2x"
  rm -rf "$tmp"
}

check_emit_status_forwards_attempts() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/status.sh"
  # shellcheck disable=SC1091
  source "$run/lib/result-emit.sh"
  local tmp; tmp="$(mktemp -d)"
  CASE_ID=c1 RUN_ID=r1 MODEL=opus \
    emit_status "$tmp/r.json" passed inner-dir sha123 5 "" 3
  assert "emit_status: forwards attempts arg" _eq "$(jq -r .attempts "$tmp/r.json")" 3
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

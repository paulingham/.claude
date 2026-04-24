#!/usr/bin/env bash
# Assertions for the validation sequence. Each returns 0 on success, 1 on
# mismatch, with a descriptive stderr line on failure. Keep callers focused
# by returning rc instead of set -e exits, so the phase runner can report
# which assertion failed before aborting the sequence.

assert_pass_rate_equals() {
  local agg="$1"; local want="$2"
  local got; got="$(jq -r .pass_rate "$agg")"
  [ "$got" = "$want" ] && return 0
  echo "[assert] pass_rate want=$want got=$got ($agg)" >&2; return 1
}

assert_verdict() {
  local report="$1"; local want="$2"
  local got; got="$(jq -r .verdict "$report")"
  [ "$got" = "$want" ] && return 0
  echo "[assert] verdict want=$want got=$got ($report)" >&2; return 1
}

assert_regression_count_ge() {
  local report="$1"; local want="$2"
  local got; got="$(jq -r .regression_count "$report")"
  [ "$got" -ge "$want" ] 2>/dev/null && return 0
  echo "[assert] regression_count want≥$want got=$got ($report)" >&2; return 1
}

assert_case_in_regressions() {
  local report="$1"; local case_id="$2"
  jq -e --arg c "$case_id" '.regressions|map(.case_id)|index($c)' "$report" >/dev/null \
    && return 0
  echo "[assert] case $case_id not in regressions ($report)" >&2; return 1
}

assert_bytes_equal() {
  local a="$1"; local b="$2"
  cmp -s "$a" "$b" && return 0
  echo "[assert] files differ: $a vs $b" >&2; return 1
}

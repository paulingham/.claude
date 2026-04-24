#!/usr/bin/env bash
# Test helpers for Story 7 run-suite.sh. Each check function performs a single
# focused assertion; keeps the test runner thin.

_eq() { [ "$1" = "$2" ]; }

check_suite_args_required() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-args.sh"
  parse_suite_args --run-id r1
  assert "suite-args: RUN_ID populated" _eq "$RUN_ID" "r1"
}

check_suite_args_defaults() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-args.sh"
  parse_suite_args --run-id r1
  assert "suite-args: default suite"         _eq "$SUITE" "default"
  assert "suite-args: default model"         _eq "$MODEL" "opus"
  assert "suite-args: default concurrency=4" _eq "$CONCURRENCY" "4"
  assert "suite-args: default harness empty" _eq "$HARNESS_REF" ""
  assert "suite-args: default resume=0"      _eq "$RESUME" "0"
}

check_suite_args_flags() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-args.sh"
  parse_suite_args --run-id r2 --suite custom --model sonnet \
    --concurrency 8 --harness-ref deadbeef --resume
  assert "suite-args: --suite"        _eq "$SUITE" "custom"
  assert "suite-args: --model"        _eq "$MODEL" "sonnet"
  assert "suite-args: --concurrency"  _eq "$CONCURRENCY" "8"
  assert "suite-args: --harness-ref"  _eq "$HARNESS_REF" "deadbeef"
  assert "suite-args: --resume"       _eq "$RESUME" "1"
}

check_resume_detection() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-resume.sh"
  local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/cases/c1"; : > "$tmp/cases/c1/result.json"
  assert     "resume: c1 done → true"        case_already_done "$tmp" c1
  assert_not "resume: c2 not done → false"   case_already_done "$tmp" c2
  rm -rf "$tmp"
}

_write_stub_result() {
  local path="$1"; local status="$2"; local cid="$3"
  mkdir -p "$(dirname "$path")"
  jq -n --arg s "$status" --arg c "$cid" \
    '{case_id:$c,run_id:"r",status:$s,duration_sec:1,cost_usd:0.25}' > "$path"
}

check_aggregate_counts() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-aggregate.sh"
  local tmp; tmp="$(mktemp -d)"
  _write_stub_result "$tmp/cases/a/result.json" passed a
  _write_stub_result "$tmp/cases/b/result.json" passed b
  _write_stub_result "$tmp/cases/c/result.json" failed_diff c
  _write_stub_result "$tmp/cases/d/result.json" failed_infra d
  aggregate_run "$tmp" r1 default opus deadbeef
  local agg="$tmp/aggregate.json"
  assert "aggregate: total=4"         _eq "$(jq -r .total_cases "$agg")" "4"
  assert "aggregate: passed=2"        _eq "$(jq -r .passed "$agg")" "2"
  assert "aggregate: failed_diff=1"   _eq "$(jq -r .failed_diff "$agg")" "1"
  assert "aggregate: failed_infra=1"  _eq "$(jq -r .failed_infra "$agg")" "1"
  rm -rf "$tmp"
}

check_aggregate_pass_rate() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-aggregate.sh"
  local tmp; tmp="$(mktemp -d)"
  _write_stub_result "$tmp/cases/a/result.json" passed a
  _write_stub_result "$tmp/cases/b/result.json" failed_diff b
  _write_stub_result "$tmp/cases/c/result.json" failed_infra c
  aggregate_run "$tmp" r1 default opus live
  assert "aggregate: pass_rate excludes failed_infra" \
    _eq "$(jq -r .pass_rate "$tmp/aggregate.json")" "0.5"
  rm -rf "$tmp"
}

check_aggregate_empty_denominator() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-aggregate.sh"
  local tmp; tmp="$(mktemp -d)"
  _write_stub_result "$tmp/cases/a/result.json" failed_infra a
  aggregate_run "$tmp" r1 default opus live
  assert "aggregate: all infra → pass_rate 0" \
    _eq "$(jq -r .pass_rate "$tmp/aggregate.json")" "0"
  rm -rf "$tmp"
}

check_resume_filter() {
  local run="$1"
  # shellcheck disable=SC1091
  source "$run/lib/suite-resume.sh"
  local tmp; tmp="$(mktemp -d)"
  mkdir -p "$tmp/cases/done"; : > "$tmp/cases/done/result.json"
  local pending
  pending="$(filter_pending_cases 1 "$tmp" done todo1 todo2 | tr '\n' ' ')"
  assert "resume: filters to pending only" _eq "$pending" "todo1 todo2 "
  pending="$(filter_pending_cases 0 "$tmp" done todo1 todo2 | tr '\n' ' ')"
  assert "resume: no-resume returns all"   _eq "$pending" "done todo1 todo2 "
  rm -rf "$tmp"
}

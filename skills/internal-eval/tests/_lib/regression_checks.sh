#!/usr/bin/env bash
# Story 8 regression-diff tests.

_eq() { [ "$1" = "$2" ]; }

_fixture_baseline() {
  local out="$1"; shift
  {
    echo "---"; echo "harness_ref: base1"; echo "model: opus"; echo "---"; echo
    echo "## Per-Case Results"; echo; echo "| case_id | status |"; echo "|---|---|"
    for pair in "$@"; do echo "| ${pair%=*} | ${pair#*=} |"; done
  } > "$out"
}

_fixture_current() {
  local run_dir="$1"; local harness="$2"; shift 2
  mkdir -p "$run_dir"
  jq -n --arg h "$harness" --argjson cases "$(_pairs_to_json "$@")" \
    '{run_id:"r2",suite:"default",model:"opus",harness_ref:$h,
      total_cases:($cases|length),passed:0,failed_diff:0,failed_build:0,
      failed_timeout:0,failed_infra:0,pass_rate:0,total_duration_sec:0,
      total_cost_usd:0,completed_at:"2026-04-24T11:00:00Z",case_results:$cases}' \
    > "$run_dir/aggregate.json"
}

_pairs_to_json() {
  local first=1; printf '['
  for pair in "$@"; do
    [ $first -eq 1 ] || printf ','; first=0
    printf '{"case_id":"%s","status":"%s"}' "${pair%=*}" "${pair#*=}"
  done; printf ']'
}

check_regressions_detected() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _fixture_baseline "$tmp/base.md" c1=passed c2=passed
  _fixture_current  "$tmp/run"  abc c1=failed_diff c2=passed
  bash "$score/diff-vs-baseline.sh" --run-id run --baseline "$tmp/base.md" \
    --runs-dir "$tmp" >/dev/null
  local reg="$tmp/run/regression.json"
  assert "regression: file exists"        is_file "$reg"
  assert "regression: regression_count=1" _eq "$(jq -r .regression_count "$reg")" 1
  assert "regression: verdict = EVAL_FAILED" _eq "$(jq -r .verdict "$reg")" "EVAL_FAILED"
  rm -rf "$tmp"
}

check_no_regressions_passed() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _fixture_baseline "$tmp/base.md" c1=passed
  _fixture_current  "$tmp/run"  abc c1=passed
  bash "$score/diff-vs-baseline.sh" --run-id run --baseline "$tmp/base.md" \
    --runs-dir "$tmp" >/dev/null
  local reg="$tmp/run/regression.json"
  assert "no-regression: verdict = EVAL_PASSED" _eq "$(jq -r .verdict "$reg")" "EVAL_PASSED"
  rm -rf "$tmp"
}

check_improvements_quadrant() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _fixture_baseline "$tmp/base.md" c1=failed_diff
  _fixture_current  "$tmp/run"  abc c1=passed
  bash "$score/diff-vs-baseline.sh" --run-id run --baseline "$tmp/base.md" \
    --runs-dir "$tmp" >/dev/null
  local reg="$tmp/run/regression.json"
  assert "improvements: 1 fail→pass"  _eq "$(jq '.improvements | length' "$reg")" 1
  assert "improvements: verdict still EVAL_PASSED" _eq "$(jq -r .verdict "$reg")" "EVAL_PASSED"
  rm -rf "$tmp"
}

check_added_removed_neutral() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _fixture_baseline "$tmp/base.md" c1=passed c_gone=passed
  _fixture_current  "$tmp/run"  abc c1=passed c_new=passed
  bash "$score/diff-vs-baseline.sh" --run-id run --baseline "$tmp/base.md" \
    --runs-dir "$tmp" >/dev/null
  local reg="$tmp/run/regression.json"
  assert "added: c_new listed"    _eq "$(jq -r '.added[0]' "$reg")" "c_new"
  assert "removed: c_gone listed" _eq "$(jq -r '.removed[0]' "$reg")" "c_gone"
  assert "added/removed neutral → EVAL_PASSED" _eq "$(jq -r .verdict "$reg")" "EVAL_PASSED"
  rm -rf "$tmp"
}

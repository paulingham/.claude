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

check_failed_infra_never_regression() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _fixture_baseline "$tmp/base.md" c1=passed
  _fixture_current  "$tmp/run"  abc c1=failed_infra
  bash "$score/diff-vs-baseline.sh" --run-id run --baseline "$tmp/base.md" \
    --runs-dir "$tmp" >/dev/null
  local reg="$tmp/run/regression.json"
  assert "infra: passed→failed_infra NOT a regression" \
    _eq "$(jq -r .regression_count "$reg")" 0
  assert "infra: verdict = EVAL_PASSED"            _eq "$(jq -r .verdict "$reg")" "EVAL_PASSED"
  rm -rf "$tmp"
}

check_failed_timeout_never_regression() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _fixture_baseline "$tmp/base.md" c1=passed
  _fixture_current  "$tmp/run"  abc c1=failed_timeout
  bash "$score/diff-vs-baseline.sh" --run-id run --baseline "$tmp/base.md" \
    --runs-dir "$tmp" >/dev/null
  local reg="$tmp/run/regression.json"
  assert "timeout: passed→failed_timeout NOT a regression" \
    _eq "$(jq -r .regression_count "$reg")" 0
  rm -rf "$tmp"
}

_fixture_case_metadata() {
  local cases_dir="$1"; local case_id="$2"; local min="$3"; local max="$4"; local tier="${5:-deterministic}"
  mkdir -p "$cases_dir/$case_id"
  jq -n --arg id "$case_id" --arg min "$min" --arg max "$max" --arg tier "$tier" \
    '{case_id:$id, classification:"bug-fix", source_pr:"", min_harness_ref:$min,
      max_harness_ref:(if $max=="" then null else $max end),
      flakiness_tier:$tier, scoring_mode:"test-passing", timeout_minutes:30,
      cost_ceiling_usd:5, synthetic:false}' \
    > "$cases_dir/$case_id/metadata.json"
}

_git_shas() {
  local repo="$1"; mkdir -p "$repo" && cd "$repo" || return
  git init -q && git config user.email t@t && git config user.name t
  touch a && git add a && git commit -q -m one && git rev-parse HEAD
  touch b && git add b && git commit -q -m two && git rev-parse HEAD
}

check_intersection_excludes_incompatible() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  local repo="$tmp/repo"; local shas; shas="$(_git_shas "$repo")"
  local sha1; sha1="$(echo "$shas" | sed -n 1p)"
  local sha2; sha2="$(echo "$shas" | sed -n 2p)"
  mkdir -p "$tmp/cases"
  _fixture_case_metadata "$tmp/cases" c_old "$sha1" "$sha1"   # incompatible with sha2
  _fixture_case_metadata "$tmp/cases" c_ok  "$sha1" ""        # compatible
  _fixture_baseline "$tmp/base.md" c_old=passed c_ok=passed
  _fixture_current "$tmp/run" "$sha2" c_old=failed_diff c_ok=passed
  EVAL_CASES_DIR="$tmp/cases" CLAUDE_HARNESS_REPO="$repo" \
    bash "$score/diff-vs-baseline.sh" --run-id run --baseline "$tmp/base.md" \
      --runs-dir "$tmp" >/dev/null
  local reg="$tmp/run/regression.json"
  assert "intersection: c_old excluded (harness-ref incompatible)" \
    _eq "$(jq -r .regression_count "$reg")" 0
  assert "intersection: intersection_count == 1" \
    _eq "$(jq -r .intersection_count "$reg")" 1
  rm -rf "$tmp"
}

check_quarantined_excluded() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  local repo="$tmp/repo"; mkdir -p "$repo"
  (cd "$repo" && git init -q && git config user.email t@t && git config user.name t \
    && touch a && git add a && git commit -q -m one)
  local sha; sha="$(cd "$repo" && git rev-parse HEAD)"
  mkdir -p "$tmp/cases"
  _fixture_case_metadata "$tmp/cases" c_q "$sha" "" quarantined
  _fixture_case_metadata "$tmp/cases" c_n "$sha" "" deterministic
  _fixture_baseline "$tmp/base.md" c_q=passed c_n=passed
  _fixture_current  "$tmp/run" "$sha" c_q=failed_diff c_n=passed
  EVAL_CASES_DIR="$tmp/cases" CLAUDE_HARNESS_REPO="$repo" \
    bash "$score/diff-vs-baseline.sh" --run-id run --baseline "$tmp/base.md" \
      --runs-dir "$tmp" >/dev/null
  local reg="$tmp/run/regression.json"
  assert "quarantined: pass→fail NOT a regression" \
    _eq "$(jq -r .regression_count "$reg")" 0
  assert "quarantined: excluded from intersection (count == 1)" \
    _eq "$(jq -r .intersection_count "$reg")" 1
  rm -rf "$tmp"
}

check_regression_md_rendered() {
  local score="$1"; local tmp; tmp="$(mktemp -d)"
  _fixture_baseline "$tmp/base.md" c1=passed c2=passed
  _fixture_current  "$tmp/run"  abc c1=failed_diff c2=passed
  bash "$score/diff-vs-baseline.sh" --run-id run --baseline "$tmp/base.md" \
    --runs-dir "$tmp" >/dev/null
  local md="$tmp/run/regression.md"
  assert "md: file exists"              is_file "$md"
  assert "md: heading present"          grep -q "^# Regression Report" "$md"
  assert "md: EVAL_FAILED shown"        grep -q "EVAL_FAILED" "$md"
  assert "md: regression row for c1"    grep -q "c1: passed → failed_diff" "$md"
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

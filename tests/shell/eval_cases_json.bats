#!/usr/bin/env bats
# A/B bridge Slice A — cases.json projection tests.
#
# A1  JSON array of per-case objects with the 6 keys
# A2  pass mirrors status==passed (passed→true, failed_diff→false)
# A3  tokens summed from tagged costs.jsonl
# A4  loc from net-numstat fixture "12\t5" → loc_added=12, loc_removed=5
# A5  absent net-numstat → loc 0,0 no crash
# A6  emitted cases.json consumed by REAL ab-compare.sh → non-INSUFFICIENT
# A7  missing costs record → tokens 0, exit 0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  mkdir -p "$WORK"

  # Source the library under test directly
  SUITE_CASES_JSON="$REPO_ROOT/skills/internal-eval/run/lib/suite-cases-json.sh"

  # Helper: set up a minimal run dir with cases
  _make_run_dir() {
    local run_dir="$1" run_id="$2"
    mkdir -p "$run_dir/cases"
    shift 2
    for case_id in "$@"; do
      mkdir -p "$run_dir/cases/$case_id"
    done
  }

  _make_result() {
    local run_dir="$1" case_id="$2" status="$3"
    echo "{\"case_id\":\"$case_id\",\"run_id\":\"r1\",\"status\":\"$status\"}" \
      > "$run_dir/cases/$case_id/result.json"
  }
}

@test "A1 write_cases_json emits JSON array with 6 keys per case" {
  local run_dir="$WORK/run1"
  _make_run_dir "$run_dir" "r1" "case-a"
  _make_result "$run_dir" "case-a" "passed"
  export EVAL_COSTS_JSONL="$WORK/empty-costs.jsonl"
  touch "$EVAL_COSTS_JSONL"

  source "$SUITE_CASES_JSON"
  write_cases_json "$run_dir" "r1"

  [ -f "$run_dir/cases.json" ]
  run jq 'type' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == '"array"' ]]

  # Check 6 required keys exist in first element
  run jq '.[0] | keys | sort' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"case"'* ]]
  [[ "$output" == *'"input_tokens"'* ]]
  [[ "$output" == *'"loc_added"'* ]]
  [[ "$output" == *'"loc_removed"'* ]]
  [[ "$output" == *'"output_tokens"'* ]]
  [[ "$output" == *'"pass"'* ]]
}

@test "A2 pass mirrors status==passed; failed_diff → false" {
  local run_dir="$WORK/run2"
  _make_run_dir "$run_dir" "r1" "pass-case" "fail-case"
  _make_result "$run_dir" "pass-case" "passed"
  _make_result "$run_dir" "fail-case" "failed_diff"
  export EVAL_COSTS_JSONL="$WORK/empty-costs2.jsonl"
  touch "$EVAL_COSTS_JSONL"

  source "$SUITE_CASES_JSON"
  write_cases_json "$run_dir" "r1"

  run jq '.[] | select(.case=="pass-case") | .pass' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == "true" ]]

  run jq '.[] | select(.case=="fail-case") | .pass' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == "false" ]]
}

@test "A3 tokens summed from tagged costs.jsonl" {
  local run_dir="$WORK/run3"
  _make_run_dir "$run_dir" "r1" "case-x"
  _make_result "$run_dir" "case-x" "passed"

  local costs="$WORK/costs3.jsonl"
  # Two records matching (eval_run_id=r1, eval_case_id=case-x)
  echo '{"eval_run_id":"r1","eval_case_id":"case-x","input_tokens":100,"output_tokens":50}' > "$costs"
  echo '{"eval_run_id":"r1","eval_case_id":"case-x","input_tokens":200,"output_tokens":75}' >> "$costs"
  # Record for different case — must not be counted
  echo '{"eval_run_id":"r1","eval_case_id":"other","input_tokens":999,"output_tokens":999}' >> "$costs"
  export EVAL_COSTS_JSONL="$costs"

  source "$SUITE_CASES_JSON"
  write_cases_json "$run_dir" "r1"

  run jq '.[] | select(.case=="case-x") | .input_tokens' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == "300" ]]

  run jq '.[] | select(.case=="case-x") | .output_tokens' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == "125" ]]
}

@test "A4 loc from net-numstat fixture 12 tab 5 -> loc_added=12 loc_removed=5" {
  local run_dir="$WORK/run4"
  _make_run_dir "$run_dir" "r1" "case-loc"
  _make_result "$run_dir" "case-loc" "passed"

  # Create inner_state_dir with net-numstat file
  local inner_dir="$run_dir/inner/case-loc"
  mkdir -p "$inner_dir"
  printf '12\t5\n' > "$inner_dir/net-numstat"

  export EVAL_COSTS_JSONL="$WORK/empty-costs4.jsonl"
  touch "$EVAL_COSTS_JSONL"

  source "$SUITE_CASES_JSON"
  write_cases_json "$run_dir" "r1"

  run jq '.[] | select(.case=="case-loc") | .loc_added' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == "12" ]]

  run jq '.[] | select(.case=="case-loc") | .loc_removed' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == "5" ]]
}

@test "A5 absent net-numstat yields loc 0,0 and exits 0" {
  local run_dir="$WORK/run5"
  _make_run_dir "$run_dir" "r1" "case-noloc"
  _make_result "$run_dir" "case-noloc" "passed"
  # No inner_state_dir at all
  export EVAL_COSTS_JSONL="$WORK/empty-costs5.jsonl"
  touch "$EVAL_COSTS_JSONL"

  source "$SUITE_CASES_JSON"
  run write_cases_json "$run_dir" "r1"
  [ "$status" -eq 0 ]

  run jq '.[] | select(.case=="case-noloc") | .loc_added' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == "0" ]]

  run jq '.[] | select(.case=="case-noloc") | .loc_removed' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == "0" ]]
}

@test "A6 cases.json consumed by real ab-compare.sh yields non-INSUFFICIENT" {
  local runs_dir="$WORK/runs6"
  local arm_a="arm-a" arm_b="arm-b"
  local run_a="$runs_dir/$arm_a"
  local run_b="$runs_dir/$arm_b"
  mkdir -p "$run_a/cases" "$run_b/cases"

  # Arm A: 2 passed cases
  for c in c1 c2; do
    mkdir -p "$run_a/cases/$c"
    echo "{\"case_id\":\"$c\",\"run_id\":\"$arm_a\",\"status\":\"passed\"}" \
      > "$run_a/cases/$c/result.json"
  done

  # Arm B: 2 passed cases
  for c in c1 c2; do
    mkdir -p "$run_b/cases/$c"
    echo "{\"case_id\":\"$c\",\"run_id\":\"$arm_b\",\"status\":\"passed\"}" \
      > "$run_b/cases/$c/result.json"
  done

  export EVAL_COSTS_JSONL="$WORK/empty-costs6.jsonl"
  touch "$EVAL_COSTS_JSONL"

  # Generate cases.json for both arms
  source "$SUITE_CASES_JSON"
  write_cases_json "$run_a" "$arm_a"
  write_cases_json "$run_b" "$arm_b"

  # Run real ab-compare.sh via EVAL_RUNS_DIR (the shipped interface)
  local ab_script="$REPO_ROOT/skills/internal-eval/score/ab-compare.sh"
  export EVAL_RUNS_DIR="$runs_dir"
  run bash "$ab_script" --arm-a "$arm_a" --arm-b "$arm_b"
  [ "$status" -eq 0 ]

  local report="${runs_dir}/${arm_a}-vs-${arm_b}/ab-report.md"
  [ -f "$report" ]
  # Must not say INSUFFICIENT for both arms having pass:true cases
  run grep -c "INSUFFICIENT" "$report" || true
  [[ "$output" != "1" ]] || {
    run grep "INSUFFICIENT" "$report"
    [[ "$output" != *"one or both arms scored 0 cases"* ]]
  }
}

@test "A8 string-valued token fields coerced to 0 — no crash, valid cases.json" {
  local run_dir="$WORK/run8"
  _make_run_dir "$run_dir" "r1" "case-strtok"
  _make_result "$run_dir" "case-strtok" "passed"

  # Malformed: token values are strings not ints
  local costs="$WORK/costs8.jsonl"
  echo '{"eval_run_id":"r1","eval_case_id":"case-strtok","input_tokens":"99","output_tokens":"42"}' > "$costs"
  export EVAL_COSTS_JSONL="$costs"

  source "$SUITE_CASES_JSON"
  run write_cases_json "$run_dir" "r1"
  [ "$status" -eq 0 ]

  run jq 'type' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == '"array"' ]]
}

@test "A7 missing costs record yields tokens 0 and exits 0" {
  local run_dir="$WORK/run7"
  _make_run_dir "$run_dir" "r1" "case-nocost"
  _make_result "$run_dir" "case-nocost" "passed"

  # costs.jsonl exists but has no matching records
  local costs="$WORK/costs7.jsonl"
  echo '{"eval_run_id":"other-run","eval_case_id":"case-nocost","input_tokens":500,"output_tokens":200}' > "$costs"
  export EVAL_COSTS_JSONL="$costs"

  source "$SUITE_CASES_JSON"
  run write_cases_json "$run_dir" "r1"
  [ "$status" -eq 0 ]

  run jq '.[] | select(.case=="case-nocost") | .input_tokens' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == "0" ]]

  run jq '.[] | select(.case=="case-nocost") | .output_tokens' "$run_dir/cases.json"
  [ "$status" -eq 0 ]
  [[ "$output" == "0" ]]
}

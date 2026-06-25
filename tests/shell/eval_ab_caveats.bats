#!/usr/bin/env bats
# A/B bridge Slice B — measurement caveats rendering tests.
#
# B8  caveats block present when n<10 AND no mutation_score
# B9  caveats block absent when n>=10 AND mutation_score present

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  AB_SCRIPT="$REPO_ROOT/skills/internal-eval/score/ab-compare.sh"
  mkdir -p "$WORK"

  _make_arm() {
    local runs_dir="$1" arm="$2" n="$3" mutation="${4:-}"
    local arm_dir="$runs_dir/$arm"
    mkdir -p "$arm_dir"
    # Build cases.json directly (projection done by suite-cases-json.sh in real flow)
    local cases="["
    for i in $(seq 1 "$n"); do
      [ "$i" -gt 1 ] && cases+=","
      if [ -n "$mutation" ]; then
        cases+="{\"case\":\"c$i\",\"pass\":true,\"loc_added\":5,\"loc_removed\":0,\"input_tokens\":100,\"output_tokens\":50,\"mutation_score\":$mutation}"
      else
        cases+="{\"case\":\"c$i\",\"pass\":true,\"loc_added\":5,\"loc_removed\":0,\"input_tokens\":100,\"output_tokens\":50}"
      fi
    done
    cases+="]"
    echo "$cases" > "$arm_dir/cases.json"
  }
}

# ─── B8: caveats present when n<10 and no mutation_score ─────────────────────
@test "B8 caveats block rendered when n<10 and no mutation_score" {
  local runs_dir="$WORK/runs-b8"
  mkdir -p "$runs_dir"
  _make_arm "$runs_dir" "arm-a" 4
  _make_arm "$runs_dir" "arm-b" 4

  export EVAL_RUNS_DIR="$runs_dir"
  export EVAL_COSTS_JSONL="$WORK/empty-costs-b8.jsonl"
  touch "$EVAL_COSTS_JSONL"

  run bash "$AB_SCRIPT" --arm-a "arm-a" --arm-b "arm-b"
  [ "$status" -eq 0 ]

  local report="$runs_dir/arm-a-vs-arm-b/ab-report.md"
  [ -f "$report" ]
  run grep -c "Measurement caveats" "$report"
  [ "$output" -ge 1 ]
}

# ─── B9: caveats absent when n>=10 and mutation_score present ────────────────
@test "B9 caveats block absent when n>=10 and mutation_score present" {
  local runs_dir="$WORK/runs-b9"
  mkdir -p "$runs_dir"
  _make_arm "$runs_dir" "arm-a" 10 "0.85"
  _make_arm "$runs_dir" "arm-b" 10 "0.85"

  export EVAL_RUNS_DIR="$runs_dir"
  export EVAL_COSTS_JSONL="$WORK/empty-costs-b9.jsonl"
  touch "$EVAL_COSTS_JSONL"

  run bash "$AB_SCRIPT" --arm-a "arm-a" --arm-b "arm-b"
  [ "$status" -eq 0 ]

  local report="$runs_dir/arm-a-vs-arm-b/ab-report.md"
  [ -f "$report" ]
  run grep -c "Measurement caveats" "$report" || true
  [[ "$output" == "0" ]]
}

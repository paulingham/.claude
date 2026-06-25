#!/usr/bin/env bats
# A/B bridge Slice B — case count parity guard tests.
#
# B10  n_a=3, n_b=4 → verdict is INSUFFICIENT (parity override)
# B11  n_a=n_b=4 → no parity override (verdict is normal comparison result)

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  AB_SCRIPT="$REPO_ROOT/skills/internal-eval/score/ab-compare.sh"
  mkdir -p "$WORK"

  _make_arm() {
    local runs_dir="$1" arm="$2" n="$3"
    local arm_dir="$runs_dir/$arm"
    mkdir -p "$arm_dir"
    local cases="["
    for i in $(seq 1 "$n"); do
      [ "$i" -gt 1 ] && cases+=","
      cases+="{\"case\":\"c$i\",\"pass\":true,\"loc_added\":5,\"loc_removed\":0,\"input_tokens\":100,\"output_tokens\":50}"
    done
    cases+="]"
    echo "$cases" > "$arm_dir/cases.json"
  }
}

# ─── B10: unequal n_a / n_b → INSUFFICIENT override ─────────────────────────
@test "B10 n_a=3 n_b=4 yields INSUFFICIENT case count mismatch override" {
  local runs_dir="$WORK/runs-b10"
  mkdir -p "$runs_dir"
  _make_arm "$runs_dir" "arm-a" 3
  _make_arm "$runs_dir" "arm-b" 4

  export EVAL_RUNS_DIR="$runs_dir"
  export EVAL_COSTS_JSONL="$WORK/empty-costs-b10.jsonl"
  touch "$EVAL_COSTS_JSONL"

  run bash "$AB_SCRIPT" --arm-a "arm-a" --arm-b "arm-b"
  [ "$status" -eq 0 ]

  local report="$runs_dir/arm-a-vs-arm-b/ab-report.md"
  [ -f "$report" ]
  run grep "INSUFFICIENT" "$report"
  [ "$status" -eq 0 ]
  [[ "$output" =~ "case count mismatch" ]]
}

# ─── B11: equal n_a = n_b → no parity override ───────────────────────────────
@test "B11 n_a=n_b=4 does not trigger parity override" {
  local runs_dir="$WORK/runs-b11"
  mkdir -p "$runs_dir"
  _make_arm "$runs_dir" "arm-a" 4
  _make_arm "$runs_dir" "arm-b" 4

  export EVAL_RUNS_DIR="$runs_dir"
  export EVAL_COSTS_JSONL="$WORK/empty-costs-b11.jsonl"
  touch "$EVAL_COSTS_JSONL"

  run bash "$AB_SCRIPT" --arm-a "arm-a" --arm-b "arm-b"
  [ "$status" -eq 0 ]

  local report="$runs_dir/arm-a-vs-arm-b/ab-report.md"
  [ -f "$report" ]
  # Must NOT contain the parity-override INSUFFICIENT message
  run grep "case count mismatch" "$report" || true
  [[ "$output" == "" ]]
}

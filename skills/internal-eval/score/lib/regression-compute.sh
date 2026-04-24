#!/usr/bin/env bash
# Regression compute: run baseline + current through quadrants.jq, assemble
# the regression.json payload with verdict + references.

_rc_dir="$(dirname "${BASH_SOURCE[0]}")"

# compute_regression_json <baseline-md> <current-agg.json> → stdout JSON
compute_regression_json() {
  local base_md="$1"; local cur_path="$2"
  local base_json; base_json="$(parse_baseline_json "$base_md")"
  local cur_json; cur_json="$(cat "$cur_path")"
  local quad; quad="$(_run_quadrants "$base_json" "$cur_json")"
  _assemble_payload "$base_md" "$base_json" "$cur_json" "$quad"
}

_run_quadrants() {
  jq -n --argjson base "$1" --argjson cur "$2" -f "$_rc_dir/quadrants.jq"
}

_assemble_payload() {
  local base_md="$1"; local base="$2"; local cur="$3"; local quad="$4"
  jq -n --arg bm "$base_md" --argjson b "$base" --argjson c "$cur" --argjson q "$quad" \
    '$q + {baseline:$bm, baseline_harness_ref:($b.harness_ref),
           run_harness_ref:($c.harness_ref),
           regression_count:($q.regressions|length),
           verdict:(if ($q.regressions|length)>0 then "EVAL_FAILED" else "EVAL_PASSED" end)}'
}

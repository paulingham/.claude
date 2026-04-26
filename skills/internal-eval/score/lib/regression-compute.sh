#!/usr/bin/env bash
# Regression compute: filter to harness-ref-compatible + non-quarantined cases,
# run quadrants.jq, assemble payload with verdict.

_rc_dir="$(dirname "${BASH_SOURCE[0]}")"
# shellcheck source=compat-filter.sh
source "$_rc_dir/compat-filter.sh"

# compute_regression_json <baseline-md> <current-agg.json> → stdout JSON
compute_regression_json() {
  local base_md="$1"; local cur_path="$2"
  local base_json; base_json="$(parse_baseline_json "$base_md")"
  local cur_json; cur_json="$(cat "$cur_path")"
  local keep; keep="$(_keep_set "$cur_json")"
  local bf; bf="$(_apply_filter "$base_json" "$keep" cases)"
  local cf; cf="$(_apply_filter "$cur_json" "$keep" case_results)"
  _finalize "$base_md" "$base_json" "$cur_json" "$bf" "$cf"
}

_keep_set() {
  local cur="$1"
  local run_sha; run_sha="$(echo "$cur" | jq -r '.harness_ref // empty')"
  filter_compatible_ids "$run_sha"
}

_apply_filter() {
  local json="$1"; local keep="$2"; local path="$3"
  [ "$keep" = "*" ] && { echo "$json"; return; }
  echo "$json" | jq --arg k "$keep" --arg p "$path" \
    '. as $o | ($k|split("\n")|map(select(length>0))) as $ids
     | .[$p] |= map(select(.case_id as $c | $ids | index($c)))'
}

_finalize() {
  local base_md="$1"; local base="$2"; local cur="$3"; local bf="$4"; local cf="$5"
  local quad; quad="$(jq -n --argjson base "$bf" --argjson cur "$cf" \
                       -f "$_rc_dir/quadrants.jq")"
  _assemble_payload "$base_md" "$base" "$cur" "$quad"
}

_assemble_payload() {
  local base_md="$1"; local base="$2"; local cur="$3"; local quad="$4"
  jq -n --arg bm "$base_md" --argjson b "$base" --argjson c "$cur" --argjson q "$quad" \
    '$q + {baseline:$bm, baseline_harness_ref:($b.harness_ref),
           run_harness_ref:($c.harness_ref),
           regression_count:($q.regressions|length),
           verdict:(if ($q.regressions|length)>0 then "EVAL_FAILED" else "EVAL_PASSED" end)}'
}

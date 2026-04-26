#!/usr/bin/env bash
# Aggregation: reads per-case result.json, writes eval/runs/{run-id}/aggregate.json.
# pass_rate excludes failed_infra from denominator (plan B4/B6).

# aggregate_run <run-dir> <run-id> <suite> <model> <harness-ref>
aggregate_run() {
  local run_dir="$1"; local run_id="$2"; local suite="$3"
  local model="$4"; local harness="$5"
  local results; results="$(_gather_results "$run_dir")"
  _write_aggregate "$run_dir/aggregate.json" "$run_id" "$suite" "$model" "$harness" "$results"
}

_gather_results() {
  find "$1/cases" -mindepth 2 -maxdepth 2 -name result.json 2>/dev/null | LC_ALL=C sort
}

_write_aggregate() {
  local out="$1"; shift
  # args remaining: run_id suite model harness files
  _invoke_jq_aggregate "$@" > "$out"
}

_invoke_jq_aggregate() {
  jq -s -f "$(dirname "${BASH_SOURCE[0]}")/suite-aggregate.jq" \
    --arg run_id "$1" --arg suite "$2" --arg model "$3" --arg harness "$4" \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" $5
}

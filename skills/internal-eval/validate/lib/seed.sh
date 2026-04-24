#!/usr/bin/env bash
# Seeds ≥3 deterministic cases into $1 (a cases-dir). Each case has the 5
# artifacts a promoted case carries (metadata, task, expected, context/, golden).
# Used by the validation sequence — NOT a replacement for backfill in production.

_seed_artifacts() {
  local d="$1"; local cid="$2"
  echo "# task for $cid" > "$d/task.md"
  echo "# expected for $cid" > "$d/expected.md"
  echo "--- golden diff $cid ---" > "$d/golden-diff/pr.patch"
}

_seed_one_case() {
  local cases="$1"; local cid="$2"; local mode="$3"
  local d="$cases/$cid"; mkdir -p "$d/context" "$d/golden-diff"
  _seed_metadata "$d" "$cid" "$mode"
  _seed_artifacts "$d" "$cid"
}

_seed_metadata() {
  local d="$1"; local cid="$2"; local mode="$3"
  jq -n --arg id "$cid" --arg mode "$mode" \
    '{case_id:$id,classification:"feature",source_pr:"",
      min_harness_ref:"0000000000000000000000000000000000000000",
      max_harness_ref:null,flakiness_tier:"deterministic",
      scoring_mode:$mode,timeout_minutes:30,cost_ceiling_usd:5,synthetic:true}' \
    > "$d/metadata.json"
}

# seed_cases <cases-dir>  -- writes 3 cases covering each scoring_mode.
seed_cases() {
  local cases="$1"; mkdir -p "$cases"
  _seed_one_case "$cases" "validate-a" "test-passing"
  _seed_one_case "$cases" "validate-b" "exact"
  _seed_one_case "$cases" "validate-c" "normalized"
}

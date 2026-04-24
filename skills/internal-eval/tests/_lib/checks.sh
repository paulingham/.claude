#!/usr/bin/env bash
# Grouped assertions for Story 1 schema test. Each function body <= 5 lines.

REQUIRED_META_KEYS=(case_id classification source_pr min_harness_ref max_harness_ref
                    flakiness_tier scoring_mode timeout_minutes cost_ceiling_usd synthetic)

assert_artifact() { local ex="$1" kind="$2" name="$3"; assert "_example/$name exists" "is_$kind" "$ex/$name"; }

check_artifacts() {
  local ex="$1"
  for spec in file:task.md dir:context file:expected.md dir:golden-diff file:metadata.json; do
    assert_artifact "$ex" "${spec%%:*}" "${spec##*:}"
  done
}

check_metadata() {
  local m="$1"
  assert "metadata.json is valid JSON" json_valid "$m"
  for k in "${REQUIRED_META_KEYS[@]}"; do assert "metadata.json has key '$k'" json_has "$m" "$k"; done
}

check_ignored_dir() {
  local r="$1" rel="$2"
  assert "$rel exists"  is_dir     "$r/$rel"
  assert "$rel ignored" is_ignored "$r" "$rel/probe"
}

check_tracked_dir() {
  local r="$1" rel="$2"
  assert "$rel exists"      is_dir      "$r/$rel"
  assert "$rel NOT ignored" not_ignored "$r" "$rel/probe"
}

check_gitignore() {
  local r="$1"
  check_ignored_dir "$r" "eval/cases/.candidates"
  check_ignored_dir "$r" "eval/runs"
  check_tracked_dir "$r" "eval/baselines"
}

check_docs() {
  local r="$1" ex="$2"
  assert "eval/README.md exists"     is_file "$r/eval/README.md"
  assert "_example/SCHEMA.md exists" is_file "$ex/SCHEMA.md"
}

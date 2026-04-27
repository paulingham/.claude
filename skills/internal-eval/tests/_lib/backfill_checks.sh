#!/usr/bin/env bash
# Story 4 grouped checks. Each function body ≤ 8 lines. PASS/FAIL from caller.
source "$(dirname "${BASH_SOURCE[0]}")/backfill_fixtures.sh"
source "$(dirname "${BASH_SOURCE[0]}")/oracle_match_checks.sh"

check_oracle_paths() {
  local f="$1/oracle-paths.json"
  assert "oracle-paths.json exists"        is_file    "$f"
  assert "oracle-paths.json is valid JSON" json_valid "$f"
  assert "oracle-paths has 'include' key"  json_has   "$f" "include"
  assert "oracle-paths has 'exclude' key"  json_has   "$f" "exclude"
}
check_privacy_banner() {
  local cap="$1" tmp; tmp="$(make_tmp_workdir "$2")"
  run_banner_missing "$cap" "$tmp"; run_banner_present "$cap" "$tmp"; rm -rf "$tmp"
}
check_oracle_match() {
  local cap="$1" tests="$2" tmp; tmp="$(make_tmp_workdir "$tests/../..")"
  run_match_positive "$cap" "$tests" "$tmp"
  run_match_negative "$cap" "$tests" "$tmp"; rm -rf "$tmp"
}
_slug_assertions() {
  local s="$1"
  assert "slug 'Simple Title' kebabs"     slug_eq "$s" "Simple Title"    "simple-title"
  assert "slug strips punct!"             slug_eq "$s" "Hey! Fix: x/y?"  "hey-fix-x-y"
  assert "slug collapses runs"            slug_eq "$s" "a----b"          "a-b"
  assert "slug trims edges"               slug_eq "$s" "--trim--"        "trim"
  assert "slug lowercases unicode-ascii"  slug_eq "$s" "Café Bug"        "caf-bug"
}
check_slug() {
  local s="$1/lib/slug.sh"
  assert "slug.sh exists" is_file "$s"; _slug_assertions "$s"
}
check_promote() {
  local cap="$1" tmp; tmp="$(make_tmp_workdir "$2")"
  run_promote_happy "$cap" "$tmp"; run_promote_dest_exists "$cap" "$tmp"
  run_promote_bad_metadata "$cap" "$tmp"; run_promote_source_missing "$cap" "$tmp"
  rm -rf "$tmp"
}
check_pr_to_case() {
  local cap="$1" tests="$2" tmp; tmp="$(make_tmp_workdir "$tests/../..")"
  run_pr_to_case_artifacts "$cap" "$tests" "$tmp"; rm -rf "$tmp"
}
check_skill_md() {
  local f="$1/skills/internal-eval/capture/SKILL.md"
  assert "capture SKILL.md documents backfill.sh"  grep_file "$f" "backfill.sh"
  assert "capture SKILL.md documents promote.sh"   grep_file "$f" "promote.sh"
  assert "capture SKILL.md documents oracle-paths" grep_file "$f" "oracle-paths.json"
}

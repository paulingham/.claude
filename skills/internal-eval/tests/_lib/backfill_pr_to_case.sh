#!/usr/bin/env bash
# gh-pr-to-case artifact assertions. Functions ≤ 5 lines.

run_pr_to_case_artifacts() {
  local cap="$1" tests="$2" tmp="$3" helper="$cap/lib/gh-pr-to-case.sh"
  assert "gh-pr-to-case.sh exists" is_file "$helper"
  write_gh_shim "$tmp" "$tests"; touch "$tmp/eval/.privacy-acked"
  _run_backfill "$tmp" "test_pr" "$cap" 1
  assert_case_artifacts "$tmp"
}

_assert_required_files() {
  local base="$1" f
  for f in metadata.json task.md expected.md; do
    assert "pr_to_case: $f exists" is_file "$base/$f"
  done
}

assert_case_artifacts() {
  local base
  base="$(find "$1/eval/cases/.candidates" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | head -1)"
  assert "pr_to_case: case dir exists" [ -n "$base" ]
  [ -z "$base" ] && return 0
  _assert_required_files "$base"
  assert "pr_to_case: golden-diff/*.patch" has_patch_file "$base"
}

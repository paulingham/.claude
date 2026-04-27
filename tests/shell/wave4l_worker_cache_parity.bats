#!/usr/bin/env bats
# Wave 4-L Slice 2: AC4 parity + AC3 cache-hit avoids gh.
#
# Runs the worker's filter pipeline in two modes against the same fixture:
#   (a) CACHE-ONLY:  cache present + gh on PATH replaced by a "fail-loudly" stub.
#                    A cache hit means zero gh subprocesses (AC3). The two stages
#                    (date filter, oracle filter) must both succeed.
#   (b) GH-ONLY:     no cache; gh on PATH is a mock that returns the same fixture.
#                    Same view JSON / file list propagated through the filter pipeline.
#
# Assertion: the merged-date string parsed from view.json AND the names list
# returned for oracle-match are byte-identical between the two modes.
# Fixture: tests/fixtures/wave4l/pr-fixture/{view.json, files.txt, diff.patch}.
#
# Regeneration: regenerate the fixture only when upstream gh JSON shape changes.
# Run `gh pr view <real-pr> --json mergedAt,number,title,body,labels,mergeCommit`
# and `gh pr diff <real-pr> --name-only` and copy the outputs in.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  FIXTURE="$REPO_ROOT/tests/fixtures/wave4l/pr-fixture"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  mkdir -p "$WORK"
  export CLAUDE_GH_CACHE_DIR="$WORK/cache-root"
  export CLAUDE_SESSION_ID="bats-par"
  PR=1234
  source "$REPO_ROOT/tests/shell/_wave4l_helpers.bash"
}

teardown() {
  unset CLAUDE_GH_CACHE_DIR CLAUDE_SESSION_ID
  unset PATH_BACKUP_RESET 2>/dev/null || true
}

@test "AC3: cache hit means zero gh subprocesses (gh stub fails loudly, run still succeeds)" {
  w4l_install_fail_gh
  w4l_seed_cache
  source "$REPO_ROOT/hooks/_lib/eval-capture-worker-filters.sh"
  view="$(ecw_fetch_view "$PR")"
  names="$(ecw_fetch_names "$PR")"
  [ -n "$view" ]
  [ -n "$names" ]
  # If gh had been invoked we'd see the "MOCK GH SHOULD NOT BE INVOKED" string in stderr,
  # but ecw_fetch_view captures stderr-redacted output. We assert by content equivalence:
  [[ "$view" == *'"mergedAt":"2026-04-15T12:34:56Z"'* ]]
  [[ "$names" == *"tests/test_flaky_thing.py"* ]]
}

@test "AC4: cache-only output byte-identical to gh-only output (filter pipeline)" {
  # Mode A: cache-only
  w4l_install_fail_gh
  w4l_seed_cache
  source "$REPO_ROOT/hooks/_lib/eval-capture-worker-filters.sh"
  view_cache="$(ecw_fetch_view "$PR")"
  names_cache="$(ecw_fetch_names "$PR")"

  # Mode B: gh-only — same fixture, no cache
  rm -rf "$CLAUDE_GH_CACHE_DIR"
  unset PATH; export PATH="/usr/bin:/bin:/usr/sbin:/sbin"
  w4l_install_mock_gh_with_fixture
  view_gh="$(ecw_fetch_view "$PR")"
  names_gh="$(ecw_fetch_names "$PR")"

  # Byte-identical comparison
  [ "$view_cache" = "$view_gh" ]
  [ "$names_cache" = "$names_gh" ]
}

@test "AC4: filter gate verdict identical (date_fresh + oracle_hits) in both modes" {
  source "$REPO_ROOT/hooks/_lib/eval-capture-worker-filters.sh"
  source "$REPO_ROOT/skills/internal-eval/capture/lib/oracle-match.sh"

  # Mode A: cache-only with failing gh (proves gate succeeds without gh)
  w4l_install_fail_gh
  w4l_seed_cache
  cd "$REPO_ROOT"  # so oracle-paths.json is found at relative path
  view_a="$(ecw_fetch_view "$PR")"
  names_a="$(ecw_fetch_names "$PR")"
  ecw_date_fresh "$view_a"; date_a=$?
  ecw_oracle_hits "$names_a"; oracle_a=$?

  # Mode B: gh-only
  rm -rf "$CLAUDE_GH_CACHE_DIR"
  unset PATH; export PATH="/usr/bin:/bin:/usr/sbin:/sbin"
  w4l_install_mock_gh_with_fixture
  cd "$REPO_ROOT"
  view_b="$(ecw_fetch_view "$PR")"
  names_b="$(ecw_fetch_names "$PR")"
  ecw_date_fresh "$view_b"; date_b=$?
  ecw_oracle_hits "$names_b"; oracle_b=$?

  [ "$date_a" -eq "$date_b" ]
  [ "$oracle_a" -eq "$oracle_b" ]
  [ "$date_a" -eq 0 ]    # date is fresh (after cutoff)
  [ "$oracle_a" -eq 0 ]  # files match oracle (test files included)
}

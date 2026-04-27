#!/usr/bin/env bats
# M5: Verify wave4l_helpers.bash exposes the shared bats helpers used by
# both wave4l_worker_cache_parity.bats and wave4l_e2e_rest_to_consumer.bats.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HELPERS="$REPO_ROOT/tests/shell/_wave4l_helpers.bash"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  mkdir -p "$WORK"
  export CLAUDE_GH_CACHE_DIR="$WORK/cache-root"
  export CLAUDE_SESSION_ID="bats-m5"
  FIXTURE="$REPO_ROOT/tests/fixtures/wave4l/pr-fixture"
  PR=1234
}

teardown() {
  unset CLAUDE_GH_CACHE_DIR CLAUDE_SESSION_ID
}

@test "M5: helpers module is sourceable" {
  source "$HELPERS"
}

@test "M5: w4l_install_fail_gh installs a gh stub that exits 99" {
  source "$HELPERS"
  w4l_install_fail_gh
  run gh anything
  [ "$status" -eq 99 ]
}

@test "M5: w4l_install_mock_gh_with_fixture serves view JSON from FIXTURE" {
  source "$HELPERS"
  w4l_install_mock_gh_with_fixture
  out="$(gh pr view 1234 --json mergedAt)"
  [[ "$out" == *'"mergedAt"'* ]]
}

@test "M5: w4l_seed_cache populates cache dir with .complete sentinel" {
  source "$HELPERS"
  w4l_seed_cache
  cd="$CLAUDE_GH_CACHE_DIR/$CLAUDE_SESSION_ID-$PR"
  [ -f "$cd/view.json" ]
  [ -f "$cd/diff.patch" ]
  [ -f "$cd/files.txt" ]
  [ -f "$cd/.complete" ]
}

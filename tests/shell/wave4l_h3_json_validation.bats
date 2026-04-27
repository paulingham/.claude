#!/usr/bin/env bats
# H3: cache-read helpers must validate view.json before returning. Malformed
# JSON returns non-zero so gh fallback fires (in ecw_fetch_view /
# pr_view_json). Without this guard, malformed cache bytes propagate to
# downstream jq calls and silently misclassify PRs.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  mkdir -p "$WORK"
  export CLAUDE_GH_CACHE_DIR="$WORK/cache"
  export CLAUDE_SESSION_ID="bats-h3"
  CACHE_DIR="$CLAUDE_GH_CACHE_DIR/bats-h3-42"
  mkdir -p "$CACHE_DIR"
}

teardown() {
  unset CLAUDE_GH_CACHE_DIR CLAUDE_SESSION_ID
}

_seed_malformed_view() {
  printf 'NOT JSON {' > "$CACHE_DIR/view.json"
  printf '{}' > "$CACHE_DIR/diff.patch"
  printf '' > "$CACHE_DIR/files.txt"
  : > "$CACHE_DIR/.complete"
}

_seed_valid_view() {
  printf '{"mergedAt":"2026-04-26T10:00:00Z"}' > "$CACHE_DIR/view.json"
  printf 'd' > "$CACHE_DIR/diff.patch"
  printf 'f' > "$CACHE_DIR/files.txt"
  : > "$CACHE_DIR/.complete"
}

@test "H3: ecw_cache_view returns non-zero on malformed JSON" {
  _seed_malformed_view
  source "$REPO_ROOT/hooks/_lib/eval-capture-worker-cache.sh"
  run ecw_cache_view 42
  [ "$status" -ne 0 ]
}

@test "H3: ecw_cache_view returns 0 on valid JSON" {
  _seed_valid_view
  source "$REPO_ROOT/hooks/_lib/eval-capture-worker-cache.sh"
  run ecw_cache_view 42
  [ "$status" -eq 0 ]
  [[ "$output" == *'"mergedAt"'* ]]
}

@test "H3: pr_view_from_cache returns non-zero on malformed JSON" {
  _seed_malformed_view
  source "$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-cache-source.sh"
  run pr_view_from_cache 42
  [ "$status" -ne 0 ]
}

@test "H3: pr_view_from_cache returns 0 on valid JSON" {
  _seed_valid_view
  source "$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-cache-source.sh"
  run pr_view_from_cache 42
  [ "$status" -eq 0 ]
  [[ "$output" == *'"mergedAt"'* ]]
}

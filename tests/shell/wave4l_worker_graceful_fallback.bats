#!/usr/bin/env bats
# Wave 4-L Slice 2: AC5 graceful fallback.
#
# Verifies the cache-tier helper degrades cleanly to the gh CLI path when
#   (a) cache directory does not exist
#   (b) cache file present but malformed JSON
#   (c) MCP server "fails to start" (no .complete sentinel ever appears)
# In all three cases, the worker filter pipeline must still complete successfully
# (exit 0) and produce the same merged date / file-list output as the pure gh path.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  mkdir -p "$WORK"
  export CLAUDE_GH_CACHE_DIR="$WORK/cache-root"
  export CLAUDE_SESSION_ID="bats-fb"

  # Mock gh: prints canned outputs, exits 0. Lives on PATH ahead of real gh.
  BIN="$WORK/bin"; mkdir -p "$BIN"
  cat > "$BIN/gh" <<'SH'
#!/usr/bin/env bash
# Mock gh for tests. Args: gh pr <subcmd> <pr> [flags]
sub="$2"
case "$sub" in
  view) echo '{"mergedAt":"2026-04-26T10:00:00Z","number":42,"title":"T","body":"B","labels":[],"mergeCommit":{"oid":"abc"}}' ;;
  diff)
    for a in "$@"; do [ "$a" = "--name-only" ] && { echo "tests/x_test.py"; exit 0; }; done
    echo "diff --git a/x b/x" ;;
esac
SH
  chmod +x "$BIN/gh"
  export PATH="$BIN:$PATH"
}

teardown() {
  unset CLAUDE_GH_CACHE_DIR CLAUDE_SESSION_ID
}

_source() {
  source "$REPO_ROOT/hooks/_lib/eval-capture-worker-cache.sh"
}

@test "cache_view returns empty when cache dir does not exist (graceful)" {
  _source
  run ecw_cache_view 42
  [ "$status" -eq 1 ]
  [ -z "$output" ]
}

@test "cache_view returns empty when .complete sentinel missing (incomplete)" {
  mkdir -p "$CLAUDE_GH_CACHE_DIR/bats-fb-42"
  echo '{}' > "$CLAUDE_GH_CACHE_DIR/bats-fb-42/view.json"
  _source
  run ecw_cache_view 42
  [ "$status" -eq 1 ]
}

@test "cache_view returns view.json content when cache complete" {
  local cd="$CLAUDE_GH_CACHE_DIR/bats-fb-42"
  mkdir -p "$cd"
  printf '{"mergedAt":"2026-04-26T10:00:00Z"}' > "$cd/view.json"
  : > "$cd/.complete"
  _source
  run ecw_cache_view 42
  [ "$status" -eq 0 ]
  [[ "$output" == *'"mergedAt":"2026-04-26T10:00:00Z"'* ]]
}

@test "cache_names returns files.txt when cache complete" {
  local cd="$CLAUDE_GH_CACHE_DIR/bats-fb-99"
  mkdir -p "$cd"
  printf 'tests/foo.bats\nhooks/bar.sh\n' > "$cd/files.txt"
  : > "$cd/.complete"
  _source
  run ecw_cache_names 99
  [ "$status" -eq 0 ]
  [[ "$output" == *"tests/foo.bats"* ]]
  [[ "$output" == *"hooks/bar.sh"* ]]
}

@test "ecw_fetch_view falls back to gh when cache absent (no crash)" {
  source "$REPO_ROOT/hooks/_lib/eval-capture-worker-filters.sh"
  run ecw_fetch_view 42
  [ "$status" -eq 0 ]
  [[ "$output" == *'"mergedAt":"2026-04-26T10:00:00Z"'* ]]
}

@test "ecw_fetch_view falls back to gh when cache view.json is malformed JSON" {
  local cd="$CLAUDE_GH_CACHE_DIR/bats-fb-42"
  mkdir -p "$cd"
  printf 'NOT JSON {' > "$cd/view.json"
  : > "$cd/.complete"
  source "$REPO_ROOT/hooks/_lib/eval-capture-worker-filters.sh"
  # H3: ecw_cache_view validates JSON; malformed content fails closed
  # (returns non-zero). ecw_fetch_view's `cache && return 0 || gh` fallback
  # therefore fires the gh path, returning the mocked gh-shape view.
  run ecw_fetch_view 42
  [ "$status" -eq 0 ]
  [[ "$output" == *'"mergedAt":"2026-04-26T10:00:00Z"'* ]]
}

#!/usr/bin/env bats
# Wave 4-L Slice 2: AC8 partial — eval-case helper reads cache first.
#
# Verifies skills/internal-eval/capture/lib/gh-pr-cache-source.sh exposes
# pr_view_from_cache, pr_diff_from_cache, pr_names_from_cache and that
# gh-pr-to-case.sh's pr_view_json/pr_diff_patch/pr_diff_names dispatch
# through the cache before falling back to gh.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  WORK="$BATS_FILE_TMPDIR/work-$BATS_TEST_NUMBER"
  mkdir -p "$WORK"
  export CLAUDE_GH_CACHE_DIR="$WORK/cache-root"
  export CLAUDE_SESSION_ID="bats-pc"
  PR=4242

  # Failing gh — tells us if a cache hit is being honored.
  BIN="$WORK/bin"; mkdir -p "$BIN"
  cat > "$BIN/gh" <<'SH'
#!/usr/bin/env bash
echo "MOCK GH SHOULD NOT BE INVOKED ON CACHE HIT" >&2
exit 99
SH
  chmod +x "$BIN/gh"
  export PATH="$BIN:$PATH"

  CD="$CLAUDE_GH_CACHE_DIR/$CLAUDE_SESSION_ID-$PR"
  mkdir -p "$CD"
  printf '{"number":4242,"title":"X","body":"Y","labels":[],"mergeCommit":{"oid":"abc"}}' > "$CD/view.json"
  printf 'diff --git a/x b/x\n' > "$CD/diff.patch"
  printf 'tests/zz_test.py\n' > "$CD/files.txt"
  : > "$CD/.complete"
}

teardown() {
  unset CLAUDE_GH_CACHE_DIR CLAUDE_SESSION_ID
}

@test "pr_view_from_cache returns view.json on cache hit" {
  source "$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-cache-source.sh"
  run pr_view_from_cache "$PR"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"number":4242'* ]]
}

@test "pr_diff_from_cache returns diff.patch on cache hit" {
  source "$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-cache-source.sh"
  run pr_diff_from_cache "$PR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"diff --git a/x b/x"* ]]
}

@test "pr_names_from_cache returns files.txt on cache hit" {
  source "$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-cache-source.sh"
  run pr_names_from_cache "$PR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"tests/zz_test.py"* ]]
}

@test "pr_view_from_cache returns nonzero on cache miss" {
  rm -rf "$CLAUDE_GH_CACHE_DIR"
  source "$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-cache-source.sh"
  run pr_view_from_cache "$PR"
  [ "$status" -eq 1 ]
}

@test "gh-pr-to-case pr_view_json hits cache (gh would fail loudly)" {
  source "$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-to-case.sh"
  run pr_view_json "$PR"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"number":4242'* ]]
}

@test "gh-pr-to-case pr_diff_names hits cache (gh would fail loudly)" {
  source "$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-to-case.sh"
  run pr_diff_names "$PR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"tests/zz_test.py"* ]]
}

@test "gh-pr-to-case pr_diff_patch hits cache (gh would fail loudly)" {
  source "$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-to-case.sh"
  run pr_diff_patch "$PR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"diff --git a/x b/x"* ]]
}

#!/usr/bin/env bats
# M2: Cache layout (default root + ${sid}-${pr} dir naming) is duplicated
# across hooks/_lib/eval-capture-worker-cache.sh, skills/internal-eval/
# capture/lib/gh-pr-cache-source.sh, and hooks/_lib/github-cache-server-lib.py.
# Extract a single source of truth: hooks/_lib/gh-cache-layout.sh.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LAYOUT="$REPO_ROOT/hooks/_lib/gh-cache-layout.sh"
  ECW_CACHE="$REPO_ROOT/hooks/_lib/eval-capture-worker-cache.sh"
  PR_CACHE="$REPO_ROOT/skills/internal-eval/capture/lib/gh-pr-cache-source.sh"
}

@test "M2: hooks/_lib/gh-cache-layout.sh exists and is sourceable" {
  [ -f "$LAYOUT" ]
  run bash -c "source '$LAYOUT' && type gh_cache_default_root"
  [ "$status" -eq 0 ]
}

@test "M2: gh_cache_default_root respects XDG_CACHE_HOME" {
  run bash -c "unset CLAUDE_GH_CACHE_DIR; export XDG_CACHE_HOME=/x; source '$LAYOUT' && gh_cache_default_root"
  [ "$status" -eq 0 ]
  [ "$output" = "/x/claude/gh-pr" ]
}

@test "M2: gh_cache_default_root falls back to HOME/.cache" {
  run bash -c "unset CLAUDE_GH_CACHE_DIR XDG_CACHE_HOME; export HOME=/h; source '$LAYOUT' && gh_cache_default_root"
  [ "$status" -eq 0 ]
  [ "$output" = "/h/.cache/claude/gh-pr" ]
}

@test "M2: gh_cache_dir_for produces SID-PR path" {
  run bash -c "unset CLAUDE_GH_CACHE_DIR XDG_CACHE_HOME; export HOME=/h; export CLAUDE_SESSION_ID=sess; source '$LAYOUT' && gh_cache_dir_for 47"
  [ "$status" -eq 0 ]
  [ "$output" = "/h/.cache/claude/gh-pr/sess-47" ]
}

@test "M2: eval-capture-worker-cache.sh sources gh-cache-layout.sh" {
  grep -q "gh-cache-layout.sh" "$ECW_CACHE"
}

@test "M2: gh-pr-cache-source.sh sources gh-cache-layout.sh" {
  grep -q "gh-cache-layout.sh" "$PR_CACHE"
}

@test "M2: insecure /tmp/gh-pr-cache default removed from shell helpers" {
  ! grep -q "/tmp/gh-pr-cache" "$ECW_CACHE"
  ! grep -q "/tmp/gh-pr-cache" "$PR_CACHE"
}

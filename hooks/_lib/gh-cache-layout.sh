#!/usr/bin/env bash
# Shared gh-PR cache layout: single source of truth for the cache root and
# per-PR directory naming used by:
#   - hooks/_lib/eval-capture-worker-cache.sh   (worker read path)
#   - skills/internal-eval/capture/lib/gh-pr-cache-source.sh (case-build path)
#   - hooks/_lib/github-cache-server-lib.py     (server write path; mirrors)
#
# Default root is XDG-respecting and never world-readable /tmp.
# Bodies ≤ 5 lines, file ≤ 50 lines.

gh_cache_default_root() {
  local xdg="${XDG_CACHE_HOME:-$HOME/.cache}"
  printf '%s/claude/gh-pr' "$xdg"
}

gh_cache_root() {
  printf '%s' "${CLAUDE_GH_CACHE_DIR:-$(gh_cache_default_root)}"
}

gh_cache_dir_for() {
  local sid="${CLAUDE_SESSION_ID:-x}"
  printf '%s/%s-%s' "$(gh_cache_root)" "$sid" "$1"
}

gh_cache_ready() {
  [ -f "$(gh_cache_dir_for "$1")/.complete" ]
}

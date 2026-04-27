#!/usr/bin/env bash
# Cache-tier helpers for eval-capture worker. Read-only against the cache
# directory written by the gh-cache MCP server. Layout per Slice 1:
#   ${CLAUDE_GH_CACHE_DIR}/${session_id}-${pr}/{view.json,diff.patch,files.txt,.complete}
# Default CLAUDE_GH_CACHE_DIR=/tmp/gh-pr-cache. All helpers fail closed
# (return 1, empty stdout) when cache is absent or incomplete — the worker
# falls through to the gh CLI path. Bodies ≤ 5 lines, file ≤ 50 lines.

ecw_cache_dir() {
  local root="${CLAUDE_GH_CACHE_DIR:-/tmp/gh-pr-cache}"
  local sid="${CLAUDE_SESSION_ID:-x}"
  printf '%s/%s-%s' "$root" "$sid" "$1"
}

ecw_cache_ready() {
  local cd; cd="$(ecw_cache_dir "$1")"
  [ -f "$cd/.complete" ]
}

ecw_cache_view() {
  ecw_cache_ready "$1" || return 1
  cat "$(ecw_cache_dir "$1")/view.json" 2>/dev/null
}

ecw_cache_diff() {
  ecw_cache_ready "$1" || return 1
  cat "$(ecw_cache_dir "$1")/diff.patch" 2>/dev/null
}

ecw_cache_names() {
  ecw_cache_ready "$1" || return 1
  cat "$(ecw_cache_dir "$1")/files.txt" 2>/dev/null
}

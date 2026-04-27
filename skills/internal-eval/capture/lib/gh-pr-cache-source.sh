#!/usr/bin/env bash
# Cache-tier source helpers for gh-pr-to-case.sh. Read-only against the
# directory written by the gh-cache MCP server. Layout per Slice 1:
#   ${CLAUDE_GH_CACHE_DIR}/${session_id}-${pr}/{view.json,diff.patch,files.txt,.complete}
# Default CLAUDE_GH_CACHE_DIR=/tmp/gh-pr-cache. All helpers fail closed
# (return 1, empty stdout) when cache is absent or incomplete — callers
# fall through to gh CLI. Bodies ≤ 5 lines, file ≤ 50 lines.

_pr_cache_dir() {
  local root="${CLAUDE_GH_CACHE_DIR:-/tmp/gh-pr-cache}"
  local sid="${CLAUDE_SESSION_ID:-x}"
  printf '%s/%s-%s' "$root" "$sid" "$1"
}

_pr_cache_ready() {
  local cd; cd="$(_pr_cache_dir "$1")"
  [ -f "$cd/.complete" ]
}

pr_view_from_cache() {
  _pr_cache_ready "$1" || return 1
  cat "$(_pr_cache_dir "$1")/view.json" 2>/dev/null
}

pr_diff_from_cache() {
  _pr_cache_ready "$1" || return 1
  cat "$(_pr_cache_dir "$1")/diff.patch" 2>/dev/null
}

pr_names_from_cache() {
  _pr_cache_ready "$1" || return 1
  cat "$(_pr_cache_dir "$1")/files.txt" 2>/dev/null
}

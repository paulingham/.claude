#!/usr/bin/env bash
# Cache-tier source helpers for gh-pr-to-case.sh. Read-only against the
# directory written by the gh-cache MCP server. Layout sourced from
# hooks/_lib/gh-cache-layout.sh — single source of truth.
# All helpers fail closed (return 1, empty stdout) when cache is absent
# or incomplete — callers fall through to gh CLI.
# Bodies ≤ 5 lines, file ≤ 50 lines.

_HERE_GHPC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../hooks/_lib" && pwd)"
# shellcheck source=/dev/null
source "$_HERE_GHPC/gh-cache-layout.sh"

_pr_cache_dir() {
  gh_cache_dir_for "$1"
}

_pr_cache_ready() {
  gh_cache_ready "$1"
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

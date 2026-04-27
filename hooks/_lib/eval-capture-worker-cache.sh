#!/usr/bin/env bash
# Cache-tier helpers for eval-capture worker. Read-only against the cache
# directory written by the gh-cache MCP server. Layout (root + dir naming)
# is sourced from gh-cache-layout.sh — single source of truth.
# All helpers fail closed (return 1, empty stdout) when cache is absent or
# incomplete; the worker falls through to the gh CLI path.
# Bodies ≤ 5 lines, file ≤ 50 lines.

_HERE_ECWC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$_HERE_ECWC/gh-cache-layout.sh"

ecw_cache_dir() {
  gh_cache_dir_for "$1"
}

ecw_cache_ready() {
  gh_cache_ready "$1"
}

_ecw_validated_json_cat() {
  local body; body="$(cat "$1" 2>/dev/null)"
  printf '%s' "$body" | jq -e . >/dev/null 2>&1 || return 1
  printf '%s' "$body"
}

ecw_cache_view() {
  ecw_cache_ready "$1" || return 1
  _ecw_validated_json_cat "$(ecw_cache_dir "$1")/view.json"
}

ecw_cache_diff() {
  ecw_cache_ready "$1" || return 1
  cat "$(ecw_cache_dir "$1")/diff.patch" 2>/dev/null
}

ecw_cache_names() {
  ecw_cache_ready "$1" || return 1
  cat "$(ecw_cache_dir "$1")/files.txt" 2>/dev/null
}

#!/usr/bin/env bash
# Helpers for hooks/vlm-critic-read-guard.sh.
# Bash 3.2 SAFE: ERE only, no regex extensions.
#
# Sourced by the read-guard to test whether an absolute file path is allowed
# for the vlm-critic agent. Patterns load from the sibling file
# vlm-critic-allow-paths.txt (one ERE per line, '#' / blank ignored).
#
# This is a parallel clone of `hooks/_lib/spec-blind-allow-paths.sh` with
# the prefix renamed to `_vlm_critic_*`. Consolidation deferred to the
# post-2026-06-09 follow-up pipeline (see
# `pipeline-state/vlm-spec-blind-common-extract-soak-end/pipeline.md`).
#
# Public function:
#   is_path_allowed_for_vlm_critic <abs-path>  — Read|Grep|Glob allowlist
#
# Returns 0 (allow) / 1 (deny). Stdout silent; callers translate to exit 2 + stderr.

_VLM_CRITIC_ALLOW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_VLM_CRITIC_ALLOW_FILE="$_VLM_CRITIC_ALLOW_DIR/vlm-critic-allow-paths.txt"

# Read non-comment, non-empty patterns from the sibling allowlist file.
# Cached in a module-scope variable to avoid re-reading on every call within
# a single hook invocation. Lines starting with `!` are exclude patterns and
# are kept in the cache prefixed with `!` so the matcher can split them.
_vlm_critic_load_patterns() {
  [[ -n "${_VLM_CRITIC_PATTERNS_CACHE:-}" ]] && return 0
  if [[ ! -f "$_VLM_CRITIC_ALLOW_FILE" ]]; then
    _VLM_CRITIC_PATTERNS_CACHE=""
    return 0
  fi
  _VLM_CRITIC_PATTERNS_CACHE="$(grep -vE '^[[:space:]]*(#|$)' "$_VLM_CRITIC_ALLOW_FILE" 2>/dev/null || true)"
}

# Test the path against the loaded patterns. Exclude patterns (lines starting
# with `!`) are evaluated FIRST — a single exclude match is a hard deny.
# Then the first include match wins (allow).
is_path_allowed_for_vlm_critic() {
  local path="$1"
  [[ -z "$path" ]] && return 1
  _vlm_critic_load_patterns
  [[ -z "$_VLM_CRITIC_PATTERNS_CACHE" ]] && return 1
  local pattern bare
  # Pass 1 — excludes.
  while IFS= read -r pattern; do
    [[ -z "$pattern" ]] && continue
    case "$pattern" in
      !*)
        bare="${pattern#!}"
        [[ "$path" =~ $bare ]] && return 1
        ;;
    esac
  done <<<"$_VLM_CRITIC_PATTERNS_CACHE"
  # Pass 2 — includes.
  while IFS= read -r pattern; do
    [[ -z "$pattern" ]] && continue
    case "$pattern" in
      !*) continue ;;
    esac
    [[ "$path" =~ $pattern ]] && return 0
  done <<<"$_VLM_CRITIC_PATTERNS_CACHE"
  return 1
}

#!/usr/bin/env bash
# Helpers for hooks/spec-blind-{read,write}-guard.sh.
# Bash 3.2 SAFE: ERE only, no regex extensions.
#
# Sourced by guards to test whether an absolute file path is allowed for the
# spec-blind-validator. Patterns load from the sibling file
# spec-blind-allow-paths.txt (one ERE per line, '#' / blank ignored).
#
# Public functions:
#   is_path_allowed_for_spec_blind <abs-path>        — Read|Grep|Glob allowlist
#   is_path_allowed_for_spec_blind_write <abs-path>  — Write|Edit allowlist (test dirs only)
#
# Returns 0 (allow) / 1 (deny). Stdout silent; callers translate to exit 2 + stderr.

_SPEC_BLIND_ALLOW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SPEC_BLIND_ALLOW_FILE="$_SPEC_BLIND_ALLOW_DIR/spec-blind-allow-paths.txt"

# Read non-comment, non-empty patterns from the sibling allowlist file.
# Cached in a module-scope variable to avoid re-reading on every call within
# a single hook invocation.
_spec_blind_load_patterns() {
  [[ -n "${_SPEC_BLIND_PATTERNS_CACHE:-}" ]] && return 0
  if [[ ! -f "$_SPEC_BLIND_ALLOW_FILE" ]]; then
    _SPEC_BLIND_PATTERNS_CACHE=""
    return 0
  fi
  _SPEC_BLIND_PATTERNS_CACHE="$(grep -vE '^[[:space:]]*(#|$)' "$_SPEC_BLIND_ALLOW_FILE" 2>/dev/null || true)"
}

# Test the path against every loaded pattern. First match wins (allow).
is_path_allowed_for_spec_blind() {
  local path="$1"
  [[ -z "$path" ]] && return 1
  _spec_blind_load_patterns
  [[ -z "$_SPEC_BLIND_PATTERNS_CACHE" ]] && return 1
  local pattern
  while IFS= read -r pattern; do
    [[ -z "$pattern" ]] && continue
    [[ "$path" =~ $pattern ]] && return 0
  done <<<"$_SPEC_BLIND_PATTERNS_CACHE"
  return 1
}

# Write/Edit allowlist is strictly tighter: tests/test/spec/__tests__ directories
# only. Even files in the read-allowlist (interface.ts, package.json, etc.) are
# read-only for the validator.
is_path_allowed_for_spec_blind_write() {
  local path="$1"
  [[ -z "$path" ]] && return 1
  case "$path" in
    */tests/*|*/test/*|*/spec/*|*/__tests__/*) return 0 ;;
  esac
  return 1
}

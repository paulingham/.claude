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
# a single hook invocation. Lines starting with `!` are exclude patterns and
# are kept in the cache prefixed with `!` so the matcher can split them.
_spec_blind_load_patterns() {
  [[ -n "${_SPEC_BLIND_PATTERNS_CACHE:-}" ]] && return 0
  if [[ ! -f "$_SPEC_BLIND_ALLOW_FILE" ]]; then
    _SPEC_BLIND_PATTERNS_CACHE=""
    return 0
  fi
  _SPEC_BLIND_PATTERNS_CACHE="$(grep -vE '^[[:space:]]*(#|$)' "$_SPEC_BLIND_ALLOW_FILE" 2>/dev/null || true)"
}

# Test the path against the loaded patterns. Exclude patterns (lines starting
# with `!`) are evaluated FIRST — a single exclude match is a hard deny.
# Then the first include match wins (allow).
is_path_allowed_for_spec_blind() {
  local path="$1"
  [[ -z "$path" ]] && return 1
  _spec_blind_load_patterns
  [[ -z "$_SPEC_BLIND_PATTERNS_CACHE" ]] && return 1
  local pattern bare
  # Pass 1 — excludes (CR-MED-4).
  while IFS= read -r pattern; do
    [[ -z "$pattern" ]] && continue
    case "$pattern" in
      !*)
        bare="${pattern#!}"
        [[ "$path" =~ $bare ]] && return 1
        ;;
    esac
  done <<<"$_SPEC_BLIND_PATTERNS_CACHE"
  # Pass 2 — includes.
  while IFS= read -r pattern; do
    [[ -z "$pattern" ]] && continue
    case "$pattern" in
      !*) continue ;;
    esac
    [[ "$path" =~ $pattern ]] && return 0
  done <<<"$_SPEC_BLIND_PATTERNS_CACHE"
  return 1
}

# Write/Edit allowlist (SEC-HIGH-2): two gates.
#   1. Path MUST be inside the repo realpath (closes absolute attack paths
#      like `/etc/cron.d/tests/evil.sh` and `~/.ssh/tests/authorized_keys`).
#   2. The repo-relative path MUST be either:
#      - `tests/...`, `test/...`, `spec/...` directly under repo root, OR
#      - any path containing `__tests__/...` as a component (the JavaScript
#        co-located-test convention is broadly used; `__tests__` is unique
#        enough that it does not appear in source tree by accident).
#   Crucially, `tests` / `test` / `spec` are NOT allowed as nested
#   substrings because `src/tests/foo.ts` is an attack vector — writes
#   into the source tree masquerading as a test file.
#
# Caller is expected to pass an already-realpath-resolved absolute path so
# symlinks at `<repo>/tests/x.ts -> src/internal.ts` cannot slip through
# (SEC-HIGH-1, enforced at the guard, not here).
is_path_allowed_for_spec_blind_write() {
  local path="$1"
  [[ -z "$path" ]] && return 1
  local repo_root repo_real
  repo_root="$(git -C "$(dirname "$path")" rev-parse --show-toplevel 2>/dev/null)"
  [[ -z "$repo_root" ]] && return 1
  # shellcheck source=/dev/null
  source "$(dirname "${BASH_SOURCE[0]}")/spec-blind-path.sh"
  repo_real="$(_spec_blind_realpath "$repo_root")"
  [[ -z "$repo_real" ]] && return 1
  # Gate 1: path MUST be under repo realpath.
  case "$path" in
    "$repo_real"/*) ;;
    *) return 1 ;;
  esac
  # Gate 2a: project-root-anchored test dirs (tests, test, spec).
  case "$path" in
    "$repo_real"/tests/*|"$repo_real"/test/*|"$repo_real"/spec/*) return 0 ;;
  esac
  # Gate 2b: __tests__ is a unique-enough convention to allow co-location.
  case "$path" in
    */__tests__/*) return 0 ;;
  esac
  return 1
}

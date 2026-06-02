#!/usr/bin/env bash
# Version pin check helper (sourced by session-start-bootstrap.sh)
# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"

_ssvc_pin_path() { echo "$HARNESS_ROOT/version-pin"; }

# Returns 0 (true) iff A < B under numeric semver ordering; 1 otherwise.
# Empty/non-numeric/malformed operands return 1 (non-comparable, do not warn).
# Pure arithmetic — never sort -V (macOS BSD sort lacks -V and string-sorts).
_ssvc_version_lt() {
  local a="$1" b="$2"
  [[ "$a" =~ ^[0-9]+(\.[0-9]+)*$ && "$b" =~ ^[0-9]+(\.[0-9]+)*$ ]] || return 1
  local -a av bv
  IFS=. read -ra av <<< "$a"
  IFS=. read -ra bv <<< "$b"
  local i ac bc
  for i in 0 1 2; do
    ac=${av[i]:-0}
    bc=${bv[i]:-0}
    (( 10#$ac < 10#$bc )) && return 0
    (( 10#$ac > 10#$bc )) && return 1
  done
  return 1
}

_ssvc_check_version() {
  local pin_file pinned running bad
  pin_file=$(_ssvc_pin_path)
  [[ -f "$pin_file" ]] || return 0
  pinned=$(cat "$pin_file" | tr -d '[:space:]')
  running=${CLAUDE_VERSION:-$(claude --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)}
  [[ -n "$running" ]] || return 0
  _ssvc_version_lt "$running" "$pinned" || return 0
  echo "VERSION FLOOR: running=${running} is below pinned floor=${pinned}" >&2
  bad="$HARNESS_ROOT/knowledge/claude-code-known-bad-versions.md"
  [[ -f "$bad" ]] && cat "$bad" >&2 || true
}

#!/usr/bin/env bash
# Shared flock-based lock for codebase-map hooks. Coordinates the
# SessionStart `codebase-map-rebuild.sh` hook with the Stop
# `codebase-map-poll.sh` hook so concurrent fires never run two
# tree-sitter-heavy rebuilds in parallel against the same project.
#
# Mirrors `hooks/_lib/learning-flock.sh` byte-for-byte in shape; the
# only differences are the lockfile prefix (`claude-codebase-map-`) and
# the env var that disables the lock for tests
# (`CLAUDE_CODEBASE_MAP_FLOCK_DISABLE`).
#
# Lockfile lives under /tmp because flock(2) requires a fd reachable
# from the same filesystem on every concurrent process. /tmp is the
# universally-writeable filesystem; survives even when $HOME is
# remapped during eval-isolation runs.
#
# Bash 3.2 SAFE. flock(1) is required; falls back to no-op (single-
# process semantics) if missing — tests mock with
# CLAUDE_CODEBASE_MAP_FLOCK_DISABLE=1.

_codebase_map_lock_path() {
  local hash="${1:-${CLAUDE_PROJECT_HASH:-local}}"
  hash="${hash//[^a-zA-Z0-9_.-]/}"
  printf '/tmp/claude-codebase-map-%s.lock' "${hash:-local}"
}

_codebase_map_flock_available() {
  [[ "${CLAUDE_CODEBASE_MAP_FLOCK_DISABLE:-0}" == "1" ]] && return 1
  command -v flock >/dev/null 2>&1
}

# Acquire a flock-held FD at fd 9 for the duration of the calling
# process. Use as: with_codebase_map_lock "$hash" -- <command...>
# Returns 0 on success (caller proceeds), 1 if the lock is held > timeout.
with_codebase_map_lock() {
  local hash="$1" timeout="${CLAUDE_CODEBASE_MAP_FLOCK_TIMEOUT:-25}"
  shift
  [[ "$1" == "--" ]] && shift
  local lockfile; lockfile=$(_codebase_map_lock_path "$hash")
  if ! _codebase_map_flock_available; then
    "$@"; return $?
  fi
  ( flock -w "$timeout" 9 || exit 1; "$@" ) 9>"$lockfile"
}

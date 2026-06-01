#!/usr/bin/env bash
# Wave-2 B11.1 — Shared flock-based lock for learning hooks.
# Coordinates auto-learn-gate.sh (Stop) and learning-gc.sh (SessionStart) so
# concurrent fires never contend on memory.sqlite VACUUM or observations.jsonl
# rotation. Lockfile lives at /tmp/claude-learning-{project-hash}.lock.
#
# Why /tmp instead of $HARNESS_DATA/learning/.lock — flock(2) requires the
# lockfile inode be reachable from the same filesystem on every concurrent
# process. /tmp is universally writeable and survives even when $HOME is
# remapped during eval-isolation runs.
#
# Bash 3.2 SAFE. flock(1) is required; fall back to no-op (single-process
# semantics) if missing — tests mock with CLAUDE_LEARNING_FLOCK_DISABLE=1.

# shellcheck source=/dev/null
source "$(dirname "${BASH_SOURCE[0]}")/harness-paths.sh"
_learning_lock_path() {
  local hash="${1:-${CLAUDE_PROJECT_HASH:-local}}"
  hash="${hash//[^a-zA-Z0-9_.-]/}"
  printf '/tmp/claude-learning-%s.lock' "${hash:-local}"
}

_learning_flock_available() {
  [[ "${CLAUDE_LEARNING_FLOCK_DISABLE:-0}" == "1" ]] && return 1
  command -v flock >/dev/null 2>&1
}

# Acquire a flock-held FD at fd 9 for the duration of the calling process.
# Use as: with_learning_lock "$hash" -- <command...>
# Returns 0 on success (caller proceeds), 1 if the lock is held > timeout.
with_learning_lock() {
  local hash="$1" timeout="${CLAUDE_LEARNING_FLOCK_TIMEOUT:-25}"
  shift
  [[ "$1" == "--" ]] && shift
  local lockfile; lockfile=$(_learning_lock_path "$hash")
  if ! _learning_flock_available; then
    "$@"; return $?
  fi
  ( flock -w "$timeout" 9 || exit 1; "$@" ) 9>"$lockfile"
}

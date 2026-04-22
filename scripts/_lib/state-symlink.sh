#!/usr/bin/env bash
# state-symlink.sh — idempotent state-sharing symlinks for session worktrees
# of the canonical harness ($HOME/.claude). Sources into new-session.sh.

_SHARED_DIRS="session-memory learning manifests"

_link_dir() {
  mkdir -p "$HOME/.claude/$1"
  ln -sfn "$HOME/.claude/$1" "$2/$1"
}

_link_sqlite() {
  mkdir -p "$HOME/.claude/db" "$1/db"
  [[ -e "$HOME/.claude/db/memory.sqlite" ]] || : >"$HOME/.claude/db/memory.sqlite"
  ln -sfn "$HOME/.claude/db/memory.sqlite" "$1/db/memory.sqlite"
}

_apply_state_symlinks() {
  local wt="$1" d
  for d in $_SHARED_DIRS; do _link_dir "$d" "$wt"; done
  _link_sqlite "$wt"
}

_check_link() {
  [[ -e "$1" ]] || echo "state-symlink: missing/dangling $1" >&2
}

_verify_symlinks() {
  local wt="$1" d
  for d in $_SHARED_DIRS; do _check_link "$wt/$d"; done
  _check_link "$wt/db/memory.sqlite"
}

#!/usr/bin/env bash
# remove-session.sh <name|slug/name> [--force]
# Removes a session worktree under ${CLAUDE_SESSIONS_ROOT:-$HOME/.claude-sessions}
# and deletes its session/<name> branch. Refuses on uncommitted changes unless --force.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib/session-paths.sh"

_die() { echo "$1" >&2; exit "${2:-1}"; }

_resolve_wt() {
  local root="$1" arg="$2" hits
  [[ "$arg" == */* ]] && { printf '%s/%s\n' "$root" "$arg"; return 0; }
  hits="$(find "$root" -mindepth 2 -maxdepth 2 -type d -name "$arg" 2>/dev/null)"
  [[ "$(echo "$hits" | grep -c .)" == "1" ]] && { printf '%s\n' "$hits"; return 0; }
  { echo "ambiguous '$arg' — use {slug}/{name}:"; echo "$hits"; } >&2; return 1
}

_repo_from_wt() {
  local common; common="$(git -C "$1" rev-parse --git-common-dir 2>/dev/null)" || return 1
  (cd "$1" && cd "$common/.." && pwd)
}

_is_clean() {
  git -C "$1" diff --quiet 2>/dev/null && git -C "$1" diff --cached --quiet 2>/dev/null \
    && [[ -z "$(git -C "$1" ls-files --others --exclude-standard 2>/dev/null)" ]]
}

_do_remove() {
  [[ "$4" -eq 1 ]] || _is_clean "$1" || _die "uncommitted changes in $1 (use --force)"
  git -C "$2" worktree remove --force "$1" 2>/dev/null || rm -rf "$1"
  git -C "$2" worktree prune
  git -C "$2" branch -D "session/$3" 2>/dev/null || true
}

main() {
  local arg="${1:-}" force=0 wt repo; [[ "${2:-}" == "--force" ]] && force=1
  [[ -n "$arg" ]] || _die "usage: remove-session.sh <name|slug/name> [--force]" 2
  wt="$(_resolve_wt "$(_sessions_root)" "$arg")" || exit 1
  repo="$(_repo_from_wt "$wt")" || _die "not a git worktree: $wt"
  _do_remove "$wt" "$repo" "$(basename "$wt")" "$force"
}

main "$@"

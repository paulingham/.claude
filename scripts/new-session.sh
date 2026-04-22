#!/usr/bin/env bash
# new-session.sh — per-session git worktree launcher (repo-agnostic).
# Args: [--repo <path>] [--name <name>] [--force] [--no-state-share]
# Worktree: ${CLAUDE_SESSIONS_ROOT:-$HOME/.claude-sessions}/<slug>/<name>.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib/session-paths.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib/session-name.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib/state-symlink.sh"
REPO="$(pwd)"; NAME=""; FORCE=0; NO_SHARE=0
_maybe_share_state() {
  _is_canonical_harness "$1" && { _apply_state_symlinks "$2"; _verify_symlinks "$2"; }; :
}
_parse_args() {
  while [[ $# -gt 0 ]]; do case "$1" in
    --repo) REPO="$2"; shift 2 ;; --name) NAME="$2"; shift 2 ;;
    --force) FORCE=1; shift ;; --no-state-share) NO_SHARE=1; shift ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac; done
}
_resolve_name() {
  [[ -n "$NAME" ]] || NAME="$(_default_name)"
  _validate_name "$NAME" || { echo "invalid name: $NAME" >&2; exit 2; }
}
_guard_existing() {
  [[ ! -e "$1" ]] && return 0
  [[ "$FORCE" -eq 1 ]] || { echo "worktree exists at $1 (use --force)" >&2; exit 1; }
  git -C "$REPO" worktree remove --force "$1" 2>/dev/null || rm -rf "$1"
  git -C "$REPO" branch -D "session/$NAME" 2>/dev/null || true
}
_create_worktree() {
  mkdir -p "$(dirname "$1")"
  git -C "$REPO" worktree add -b "session/$NAME" "$1" >/dev/null \
    || { git -C "$REPO" branch -D "session/$NAME" 2>/dev/null || true; exit 1; }
}
main() {
  _parse_args "$@"; _resolve_name
  local wt; wt="$(_session_path "$REPO" "$NAME")"
  _guard_existing "$wt"; _create_worktree "$wt"
  [[ "$NO_SHARE" -eq 1 ]] || _maybe_share_state "$REPO" "$wt"
  printf '\ncd %s\nclaude\n' "$wt"
}
main "$@"

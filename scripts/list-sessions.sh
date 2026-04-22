#!/usr/bin/env bash
# list-sessions.sh — list session worktrees under ${CLAUDE_SESSIONS_ROOT:-$HOME/.claude-sessions}.
# Groups by repo slug (directory name); shows branch + last commit subject + age.
# Ignores worktrees whose HEAD is not on a session/* branch.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib/session-paths.sh"

_print_entry() {
  local wt="$1" b s a
  b="$(git -C "$wt" rev-parse --abbrev-ref HEAD 2>/dev/null)" && [[ "$b" == session/* ]] || return 0
  s="$(git -C "$wt" log -1 --pretty=%s 2>/dev/null)"
  a="$(git -C "$wt" log -1 --pretty=%cr 2>/dev/null)"
  printf '  %s  %s  [%s]  %s\n' "$(basename "$wt")" "$b" "$a" "$s"
}

_print_slug() {
  local slug_dir="$1"
  printf '%s:\n' "$(basename "$slug_dir")"
  for wt in "$slug_dir"/*/; do [[ -d "$wt" ]] && _print_entry "${wt%/}"; done
}

main() {
  local root; root="$(_sessions_root)"
  if [[ ! -d "$root" ]] || [[ -z "$(ls -A "$root" 2>/dev/null)" ]]; then
    echo "No active sessions."; return 0
  fi
  for slug in "$root"/*/; do [[ -d "$slug" ]] && _print_slug "${slug%/}"; done
}

main "$@"

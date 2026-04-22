#!/usr/bin/env bash
# session-paths.sh — path helpers for new-session.sh.
# _repo_slug: lowercase basename with non-alphanumerics collapsed to dashes.
# _sessions_root: $CLAUDE_SESSIONS_ROOT else $HOME/.claude-sessions.
# _session_path: <root>/<slug>/<name>.

_repo_slug() {
  basename "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed 's/^-*//;s/-*$//'
}

_sessions_root() {
  echo "${CLAUDE_SESSIONS_ROOT:-$HOME/.claude-sessions}"
}

_session_path() {
  echo "$(_sessions_root)/$(_repo_slug "$1")/$2"
}

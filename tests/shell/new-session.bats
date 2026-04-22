#!/usr/bin/env bats
# Specs for scripts/new-session.sh and its _lib/ helpers.
# Each test sets CLAUDE_SESSIONS_ROOT to a temp dir and creates a throwaway
# git repo at /tmp/ns_<pid>_<n> so the system's real state is never touched.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  SCRIPTS_DIR="$REPO_ROOT/scripts"
  SESSIONS_ROOT="$(mktemp -d)"
  TESTREPO="$(mktemp -d)/testrepo"
  mkdir -p "$TESTREPO"
  (
    cd "$TESTREPO" || exit 1
    git init -q -b main
    git config user.email ci@example.com
    git config user.name ci
    echo initial > README.md
    git add README.md
    git commit -q -m initial
  )
  export CLAUDE_SESSIONS_ROOT="$SESSIONS_ROOT"
}

teardown() {
  if [[ -d "$SESSIONS_ROOT" ]]; then
    while IFS= read -r wt; do
      [[ -n "$wt" ]] && git -C "$TESTREPO" worktree remove --force "$wt" 2>/dev/null || true
    done < <(find "$SESSIONS_ROOT" -mindepth 2 -maxdepth 2 -type d 2>/dev/null)
  fi
  rm -rf "$SESSIONS_ROOT" "$(dirname "$TESTREPO")" 2>/dev/null || true
}

# ---------- _repo_slug (helper) ----------

@test "_repo_slug normalises basename: uppercase and non-alnum become lowercase+dash" {
  run bash -c "source '$LIB_DIR/session-paths.sh'; _repo_slug /tmp/My_Repo.Git"
  [ "$status" -eq 0 ]
  [ "$output" = "my-repo-git" ]
}

@test "_sessions_root honours CLAUDE_SESSIONS_ROOT, else defaults to HOME/.claude-sessions" {
  run bash -c "unset CLAUDE_SESSIONS_ROOT; export HOME=/tmp/h; source '$LIB_DIR/session-paths.sh'; _sessions_root"
  [ "$output" = "/tmp/h/.claude-sessions" ]
  run bash -c "export CLAUDE_SESSIONS_ROOT=/foo; source '$LIB_DIR/session-paths.sh'; _sessions_root"
  [ "$output" = "/foo" ]
}

@test "_session_path composes root/slug/name" {
  run bash -c "export CLAUDE_SESSIONS_ROOT=/s; source '$LIB_DIR/session-paths.sh'; _session_path /tmp/testrepo foo"
  [ "$status" -eq 0 ]
  [ "$output" = "/s/testrepo/foo" ]
}

# ---------- _default_name (AC5a.4) ----------

@test "_default_name matches YYYYMMDD-HHMMSS-xxxx with lowercase alphanumeric suffix" {
  run bash -c "source '$LIB_DIR/session-name.sh'; _default_name"
  [ "$status" -eq 0 ]
  [[ "$output" =~ ^[0-9]{8}-[0-9]{6}-[a-z0-9]{4}$ ]]
}

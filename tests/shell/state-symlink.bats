#!/usr/bin/env bats
# Specs for scripts/_lib/state-symlink.sh and new-session.sh integration.
# Each test sets HOME to a temp dir and stages a fake harness so the real
# $HOME/.claude/{session-memory,learning,manifests,db} is never touched.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  SCRIPTS_DIR="$REPO_ROOT/scripts"
  FAKE_HOME="$(mktemp -d)"
  WORK_DIR="$(mktemp -d)"
  SESSIONS_ROOT="$(mktemp -d)"
  FAKE_HARNESS="$FAKE_HOME/.claude"
  mkdir -p "$FAKE_HARNESS"
  (
    cd "$FAKE_HARNESS" || exit 1
    git init -q -b main
    git config user.email ci@example.com
    git config user.name ci
    echo harness > README.md
    git add README.md
    git commit -q -m initial
  )
  export HOME="$FAKE_HOME"
  export CLAUDE_SESSIONS_ROOT="$SESSIONS_ROOT"
}

teardown() {
  if [[ -d "$SESSIONS_ROOT" ]]; then
    while IFS= read -r wt; do
      [[ -n "$wt" ]] && git -C "$FAKE_HARNESS" worktree remove --force "$wt" 2>/dev/null || true
    done < <(find "$SESSIONS_ROOT" -mindepth 2 -maxdepth 2 -type d 2>/dev/null)
  fi
  rm -rf "$FAKE_HOME" "$WORK_DIR" "$SESSIONS_ROOT" 2>/dev/null || true
}

# ---------- _apply_state_symlinks unit behavior ----------

@test "state-symlink.sh is sourceable and exposes _apply_state_symlinks + _verify_symlinks" {
  run bash -c "source '$LIB_DIR/state-symlink.sh'; declare -f _apply_state_symlinks >/dev/null && declare -f _verify_symlinks >/dev/null && echo OK"
  [ "$status" -eq 0 ]
  [ "$output" = "OK" ]
}

_seed_harness_state() {
  mkdir -p "$FAKE_HARNESS/session-memory" "$FAKE_HARNESS/learning" "$FAKE_HARNESS/manifests" "$FAKE_HARNESS/db"
  : >"$FAKE_HARNESS/db/memory.sqlite"
}

@test "AC5c.5: target dirs and sqlite file are created before linking if missing" {
  # harness exists but no session-memory/learning/manifests/db yet
  local wt="$WORK_DIR/session-wt2"
  mkdir -p "$wt"
  run bash -c "source '$LIB_DIR/state-symlink.sh'; _apply_state_symlinks '$wt'"
  [ "$status" -eq 0 ]
  [ -d "$FAKE_HARNESS/session-memory" ]
  [ -d "$FAKE_HARNESS/learning" ]
  [ -d "$FAKE_HARNESS/manifests" ]
  [ -f "$FAKE_HARNESS/db/memory.sqlite" ]
  [ -L "$wt/session-memory" ]
  [ -L "$wt/db/memory.sqlite" ]
}

@test "idempotent: second invocation re-links without error" {
  _seed_harness_state
  local wt="$WORK_DIR/session-wt-idem"
  mkdir -p "$wt"
  run bash -c "source '$LIB_DIR/state-symlink.sh'; _apply_state_symlinks '$wt' && _apply_state_symlinks '$wt'"
  [ "$status" -eq 0 ]
  [ -L "$wt/session-memory" ]
  [ -L "$wt/db/memory.sqlite" ]
}

@test "_verify_symlinks logs missing/dangling links to stderr" {
  local wt="$WORK_DIR/session-wt-verify"
  mkdir -p "$wt/db"
  # Plant a dangling symlink
  ln -sfn "/nonexistent/path" "$wt/session-memory"
  run bash -c "source '$LIB_DIR/state-symlink.sh'; _verify_symlinks '$wt' 2>&1 1>/dev/null"
  [ "$status" -eq 0 ]
  [[ "$output" == *"session-memory"* ]]
}

@test "AC5c.1: _apply_state_symlinks creates 4 symlinks into a harness worktree" {
  _seed_harness_state
  local wt="$WORK_DIR/session-wt"
  mkdir -p "$wt/db"
  run bash -c "source '$LIB_DIR/state-symlink.sh'; _apply_state_symlinks '$wt'"
  [ "$status" -eq 0 ]
  [ -L "$wt/session-memory" ]
  [ -L "$wt/learning" ]
  [ -L "$wt/manifests" ]
  [ -L "$wt/db/memory.sqlite" ]
  [ "$(readlink "$wt/session-memory")" = "$FAKE_HARNESS/session-memory" ]
  [ "$(readlink "$wt/learning")" = "$FAKE_HARNESS/learning" ]
  [ "$(readlink "$wt/manifests")" = "$FAKE_HARNESS/manifests" ]
  [ "$(readlink "$wt/db/memory.sqlite")" = "$FAKE_HARNESS/db/memory.sqlite" ]
}

#!/usr/bin/env bats
# Specs for scripts/list-sessions.sh and scripts/remove-session.sh (Slice 5b).
# Each test uses a throwaway CLAUDE_SESSIONS_ROOT and two temp git repos so
# the host's real state is never touched. Sessions are created via
# scripts/new-session.sh (finalised in Slice 5a).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  SCRIPTS_DIR="$REPO_ROOT/scripts"
  SESSIONS_ROOT="$(mktemp -d)"
  WORK_DIR="$(mktemp -d)"
  REPO_A="$WORK_DIR/alpha"
  REPO_B="$WORK_DIR/beta"
  for r in "$REPO_A" "$REPO_B"; do
    mkdir -p "$r"
    (
      cd "$r" || exit 1
      git init -q -b main
      git config user.email ci@example.com
      git config user.name ci
      echo init > README.md
      git add README.md
      git commit -q -m "seed for $(basename "$r")"
    )
  done
  export CLAUDE_SESSIONS_ROOT="$SESSIONS_ROOT"
}

teardown() {
  if [[ -d "$SESSIONS_ROOT" ]]; then
    while IFS= read -r wt; do
      [[ -z "$wt" ]] && continue
      for r in "$REPO_A" "$REPO_B"; do
        [[ -d "$r" ]] && git -C "$r" worktree remove --force "$wt" 2>/dev/null || true
      done
    done < <(find "$SESSIONS_ROOT" -mindepth 2 -maxdepth 2 -type d 2>/dev/null)
  fi
  rm -rf "$SESSIONS_ROOT" "$WORK_DIR" 2>/dev/null || true
}

# ---------- remove-session.sh ----------

@test "AC5b.3: remove-session removes clean worktree and deletes session/<name> branch" {
  bash "$SCRIPTS_DIR/new-session.sh" --repo "$REPO_A" --name foo >/dev/null
  local wt="$SESSIONS_ROOT/alpha/foo"
  [ -d "$wt" ]
  run bash "$SCRIPTS_DIR/remove-session.sh" foo
  [ "$status" -eq 0 ]
  [ ! -d "$wt" ]
  run git -C "$REPO_A" branch --list "session/foo"
  [ -z "$output" ]
}

@test "AC5b.4a: remove-session refuses when uncommitted changes present (exit 1)" {
  bash "$SCRIPTS_DIR/new-session.sh" --repo "$REPO_A" --name foo >/dev/null
  local wt="$SESSIONS_ROOT/alpha/foo"
  echo dirty > "$wt/newfile.txt"
  run bash "$SCRIPTS_DIR/remove-session.sh" foo
  [ "$status" -eq 1 ]
  [[ "$output" == *"uncommitted"* ]]
  [ -d "$wt" ]
}

@test "AC5b.4b: remove-session --force overrides uncommitted-changes guard" {
  bash "$SCRIPTS_DIR/new-session.sh" --repo "$REPO_A" --name foo >/dev/null
  local wt="$SESSIONS_ROOT/alpha/foo"
  echo dirty > "$wt/newfile.txt"
  run bash "$SCRIPTS_DIR/remove-session.sh" foo --force
  [ "$status" -eq 0 ]
  [ ! -d "$wt" ]
  run git -C "$REPO_A" branch --list "session/foo"
  [ -z "$output" ]
}

@test "AC5b.5: remove-session errors on ambiguous name across two repos" {
  bash "$SCRIPTS_DIR/new-session.sh" --repo "$REPO_A" --name bar >/dev/null
  bash "$SCRIPTS_DIR/new-session.sh" --repo "$REPO_B" --name bar >/dev/null
  run bash "$SCRIPTS_DIR/remove-session.sh" bar
  [ "$status" -eq 1 ]
  [[ "$output" == *"ambiguous"* ]]
  [[ "$output" == *"alpha/bar"* ]]
  [[ "$output" == *"beta/bar"* ]]
  [ -d "$SESSIONS_ROOT/alpha/bar" ]
  [ -d "$SESSIONS_ROOT/beta/bar" ]
}

@test "AC5b.5b: remove-session accepts {slug}/{name} to disambiguate" {
  bash "$SCRIPTS_DIR/new-session.sh" --repo "$REPO_A" --name bar >/dev/null
  bash "$SCRIPTS_DIR/new-session.sh" --repo "$REPO_B" --name bar >/dev/null
  run bash "$SCRIPTS_DIR/remove-session.sh" alpha/bar
  [ "$status" -eq 0 ]
  [ ! -d "$SESSIONS_ROOT/alpha/bar" ]
  [ -d "$SESSIONS_ROOT/beta/bar" ]
  run git -C "$REPO_A" branch --list "session/bar"
  [ -z "$output" ]
  run git -C "$REPO_B" branch --list "session/bar"
  [[ "$output" == *"session/bar"* ]]
}

@test "AC5b.6: shellcheck clean on list-sessions.sh and remove-session.sh" {
  if ! command -v shellcheck >/dev/null 2>&1; then skip "shellcheck not installed"; fi
  run shellcheck "$SCRIPTS_DIR/list-sessions.sh" "$SCRIPTS_DIR/remove-session.sh"
  [ "$status" -eq 0 ]
}

@test "AC5b.6: bash -n clean on list-sessions.sh and remove-session.sh" {
  run bash -n "$SCRIPTS_DIR/list-sessions.sh"
  [ "$status" -eq 0 ]
  run bash -n "$SCRIPTS_DIR/remove-session.sh"
  [ "$status" -eq 0 ]
}

# ---------- list-sessions.sh ----------

@test "AC5b.1: list-sessions on empty root prints 'No active sessions.' exit 0" {
  run bash "$SCRIPTS_DIR/list-sessions.sh"
  [ "$status" -eq 0 ]
  [ "$output" = "No active sessions." ]
}

@test "AC5b.2: list-sessions prints two sessions grouped under their repo slugs" {
  bash "$SCRIPTS_DIR/new-session.sh" --repo "$REPO_A" --name foo >/dev/null
  bash "$SCRIPTS_DIR/new-session.sh" --repo "$REPO_B" --name bar >/dev/null
  run bash "$SCRIPTS_DIR/list-sessions.sh"
  [ "$status" -eq 0 ]
  [[ "$output" == *"alpha"* ]]
  [[ "$output" == *"beta"* ]]
  [[ "$output" == *"foo"* ]]
  [[ "$output" == *"bar"* ]]
  [[ "$output" == *"session/foo"* ]]
  [[ "$output" == *"session/bar"* ]]
  [[ "$output" == *"seed for alpha"* ]]
  [[ "$output" == *"seed for beta"* ]]
}

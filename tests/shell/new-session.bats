#!/usr/bin/env bats
# Specs for scripts/new-session.sh and its _lib/ helpers.
# Each test sets CLAUDE_SESSIONS_ROOT to a temp dir and creates a throwaway
# git repo under $WORK_DIR so the system's real state is never touched.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  SCRIPTS_DIR="$REPO_ROOT/scripts"
  SESSIONS_ROOT="$(mktemp -d)"
  WORK_DIR="$(mktemp -d)"
  TESTREPO="$WORK_DIR/testrepo"
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
  rm -rf "$SESSIONS_ROOT" "$WORK_DIR" 2>/dev/null || true
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

@test "_validate_name accepts plain names and rejects empty/slash/whitespace" {
  run bash -c "source '$LIB_DIR/session-name.sh'; _validate_name foo"
  [ "$status" -eq 0 ]
  run bash -c "source '$LIB_DIR/session-name.sh'; _validate_name ''"
  [ "$status" -ne 0 ]
  run bash -c "source '$LIB_DIR/session-name.sh'; _validate_name 'a/b'"
  [ "$status" -ne 0 ]
  run bash -c "source '$LIB_DIR/session-name.sh'; _validate_name 'a b'"
  [ "$status" -ne 0 ]
}

# ---------- new-session.sh integration ----------

@test "AC5a.1: --repo --name creates worktree at <root>/<slug>/<name> on branch session/<name>" {
  run bash "$SCRIPTS_DIR/new-session.sh" --repo "$TESTREPO" --name foo
  [ "$status" -eq 0 ]
  local wt="$SESSIONS_ROOT/testrepo/foo"
  [ -d "$wt" ]
  [ -d "$wt/.git" ] || [ -f "$wt/.git" ]
  run git -C "$wt" rev-parse --abbrev-ref HEAD
  [ "$output" = "session/foo" ]
  [ -f "$wt/README.md" ]
}

@test "AC5a.2: second invocation without --force exits 1 with clear error citing path" {
  run bash "$SCRIPTS_DIR/new-session.sh" --repo "$TESTREPO" --name foo
  [ "$status" -eq 0 ]
  run bash "$SCRIPTS_DIR/new-session.sh" --repo "$TESTREPO" --name foo
  [ "$status" -eq 1 ]
  [[ "$output" == *"$SESSIONS_ROOT/testrepo/foo"* ]]
  [[ "$output" == *"--force"* ]]
}

@test "AC5a.5: --repo omitted defaults to \$(pwd); worktree is created against CWD repo" {
  cd "$TESTREPO" || exit 1
  run bash "$SCRIPTS_DIR/new-session.sh" --name bar
  [ "$status" -eq 0 ]
  local wt="$SESSIONS_ROOT/testrepo/bar"
  [ -d "$wt" ]
  run git -C "$wt" rev-parse --abbrev-ref HEAD
  [ "$output" = "session/bar" ]
}

@test "AC5a.6: output includes literal 'cd <wt>' and 'claude' on separate lines" {
  run bash "$SCRIPTS_DIR/new-session.sh" --repo "$TESTREPO" --name baz
  [ "$status" -eq 0 ]
  local wt="$SESSIONS_ROOT/testrepo/baz"
  grep -Fx "cd $wt" <<< "$output"
  grep -Fx "claude" <<< "$output"
}

@test "AC5a.3: --force removes and recreates the worktree (new HEAD, same name)" {
  run bash "$SCRIPTS_DIR/new-session.sh" --repo "$TESTREPO" --name foo
  [ "$status" -eq 0 ]
  local wt="$SESSIONS_ROOT/testrepo/foo"
  local head_before; head_before=$(git -C "$wt" rev-parse HEAD)
  # make a new commit on main of the target repo so the new worktree's HEAD differs
  (cd "$TESTREPO" && echo more >> README.md && git add README.md && git -c user.email=c@e -c user.name=c commit -q -m more)
  run bash "$SCRIPTS_DIR/new-session.sh" --repo "$TESTREPO" --name foo --force
  [ "$status" -eq 0 ]
  [ -d "$wt" ]
  local head_after; head_after=$(git -C "$wt" rev-parse HEAD)
  [ "$head_before" != "$head_after" ]
  run git -C "$wt" rev-parse --abbrev-ref HEAD
  [ "$output" = "session/foo" ]
}

@test "AC5a.8: shellcheck clean on new-session.sh and both _lib helpers" {
  if ! command -v shellcheck >/dev/null 2>&1; then skip "shellcheck not installed"; fi
  run shellcheck "$SCRIPTS_DIR/new-session.sh" "$LIB_DIR/session-paths.sh" "$LIB_DIR/session-name.sh"
  [ "$status" -eq 0 ]
}

@test "AC5a.8: bash -n clean on new-session.sh and both _lib helpers" {
  run bash -n "$SCRIPTS_DIR/new-session.sh"
  [ "$status" -eq 0 ]
  run bash -n "$LIB_DIR/session-paths.sh"
  [ "$status" -eq 0 ]
  run bash -n "$LIB_DIR/session-name.sh"
  [ "$status" -eq 0 ]
}

@test "AC5a.9: concurrent invocations yield exactly one valid worktree, no dangling branch" {
  local sh="$SCRIPTS_DIR/new-session.sh" rep="$TESTREPO"
  local la; la=$(mktemp); local lb; lb=$(mktemp)
  bash "$sh" --repo "$rep" --name foo >"$la" 2>&1 &
  local pid_a=$!
  bash "$sh" --repo "$rep" --name foo >"$lb" 2>&1 &
  local pid_b=$!
  local a=0 b=0
  wait "$pid_a" || a=$?
  wait "$pid_b" || b=$?
  local wins=$(( (a == 0) + (b == 0) ))
  [ "$wins" = "1" ] || {
    echo "A rc=$a log:$(cat "$la")"; echo "B rc=$b log:$(cat "$lb")"; false
  }
  # exactly one session/foo branch
  local branches; branches=$(git -C "$rep" branch --list "session/foo" | wc -l | tr -d ' ')
  [ "$branches" = "1" ]
  # exactly one worktree for it
  local wts; wts=$(git -C "$rep" worktree list | grep -c "\[session/foo\]" || true)
  [ "$wts" = "1" ]
  rm -f "$la" "$lb"
}

@test "AC5a.10: --repo pointed at an existing worktree creates session worktree against common-dir" {
  # pre-create an agent-style worktree (linked to the testrepo common-dir)
  local agent_wt="$WORK_DIR/agent-wt"
  mkdir -p "$(dirname "$agent_wt")"
  run git -C "$TESTREPO" worktree add -b agent-feature "$agent_wt"
  [ "$status" -eq 0 ]
  # now run new-session.sh against that worktree path
  run bash "$SCRIPTS_DIR/new-session.sh" --repo "$agent_wt" --name session-in-wt
  [ "$status" -eq 0 ]
  # session worktree exists and is on session/<name>
  local slug; slug=$(basename "$agent_wt" | tr '[:upper:]' '[:lower:]')
  local swt="$SESSIONS_ROOT/$slug/session-in-wt"
  [ -d "$swt" ]
  run git -C "$swt" rev-parse --abbrev-ref HEAD
  [ "$output" = "session/session-in-wt" ]
  # main repo's git worktree list sees the new session worktree
  run bash -c "git -C '$TESTREPO' worktree list | grep -F '$swt'"
  [ "$status" -eq 0 ]
  # original agent worktree is not disturbed
  run git -C "$agent_wt" rev-parse --abbrev-ref HEAD
  [ "$output" = "agent-feature" ]
  git -C "$TESTREPO" worktree remove --force "$swt" 2>/dev/null || true
  git -C "$TESTREPO" worktree remove --force "$agent_wt" 2>/dev/null || true
}

@test "AC5a.7: nested git worktree add inside a session worktree succeeds" {
  run bash "$SCRIPTS_DIR/new-session.sh" --repo "$TESTREPO" --name outer
  [ "$status" -eq 0 ]
  local outer="$SESSIONS_ROOT/testrepo/outer"
  local nested="$SESSIONS_ROOT/testrepo/outer-nested"
  run git -C "$outer" worktree add -b "agent/inner" "$nested"
  [ "$status" -eq 0 ]
  [ -d "$nested" ]
  run git -C "$nested" rev-parse --abbrev-ref HEAD
  [ "$output" = "agent/inner" ]
  git -C "$outer" worktree remove --force "$nested" || rm -rf "$nested"
}

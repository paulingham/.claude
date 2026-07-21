#!/usr/bin/env bats
# Specs for hooks/session-start-bootstrap.sh — the gear-routing welcome block.
#
# The bootstrap hook prints a skill list and iron laws but historically never
# mentioned how a request is classified into the PAIR / BUILD / PIPELINE gears.
# This block tells users (and the model) what gear their prompt landed in and how
# to steer into each. These specs assert the block is present, names all three
# gears, sits between SKILL AWARENESS BOOTSTRAP: and IRON LAWS:, and references
# protocols/work-class-routing.md WITHOUT introducing a bare slash-command (which
# would fire tests/shell/skill-ref-canary.bats).
#
# Hermetic: FAKE_HOME + a git stub give the hook a deterministic environment so it
# never touches the real filesystem.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/session-start-bootstrap.sh"

  FAKE_HOME="$(mktemp -d)"
  GIT_STUB_DIR="$(mktemp -d)"

  cat >"$GIT_STUB_DIR/git" <<'STUBEOF'
#!/usr/bin/env bash
case "$1 $2 $3" in
  "remote get-url origin")
    printf 'https://github.com/test-org/test-repo.git'
    exit 0
    ;;
  "rev-parse --git-dir ")
    echo ".git"
    exit 0
    ;;
  "worktree list --porcelain")
    echo "worktree /tmp/fake-main"
    echo "HEAD 0000000000000000000000000000000000000000"
    echo "branch refs/heads/main"
    exit 0
    ;;
  "rev-parse --show-toplevel ")
    exit 0
    ;;
esac
exit 0
STUBEOF
  chmod +x "$GIT_STUB_DIR/git"

  WORK_DIR="$FAKE_HOME/work"
  mkdir -p "$WORK_DIR"
}

teardown() {
  rm -rf "$FAKE_HOME" "$GIT_STUB_DIR"
}

# Helper: run the hook with FAKE_HOME and the git stub on PATH.
_run_hook() {
  cd "$WORK_DIR"
  HOME="$FAKE_HOME" PATH="$GIT_STUB_DIR:$PATH" bash "$HOOK"
}

# ---------------------------------------------------------------------------
# (a) The gear block header is present.
# ---------------------------------------------------------------------------

@test "gear-welcome: output contains the HOW WORK IS ROUTED header" {
  run _run_hook
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "HOW WORK IS ROUTED"
}

# ---------------------------------------------------------------------------
# (b) All three gear names appear.
# ---------------------------------------------------------------------------

@test "gear-welcome: output names all three gears PAIR, BUILD, PIPELINE" {
  run _run_hook
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "PAIR"
  echo "$output" | grep -q "BUILD"
  echo "$output" | grep -q "PIPELINE"
}

# ---------------------------------------------------------------------------
# (c) The gear block sits AFTER SKILL AWARENESS BOOTSTRAP: and BEFORE IRON LAWS:
#     (line-number ordering — same technique the bootstrap test uses).
# ---------------------------------------------------------------------------

@test "gear-welcome: HOW WORK IS ROUTED appears after SKILL AWARENESS and before IRON LAWS" {
  run _run_hook
  [ "$status" -eq 0 ]
  SKILL_LINE=$(echo "$output" | grep -n "SKILL AWARENESS BOOTSTRAP:" | head -1 | cut -d: -f1)
  GEAR_LINE=$(echo "$output" | grep -n "HOW WORK IS ROUTED" | head -1 | cut -d: -f1)
  IRON_LINE=$(echo "$output" | grep -n "IRON LAWS:" | head -1 | cut -d: -f1)
  [ -n "$SKILL_LINE" ]
  [ -n "$GEAR_LINE" ]
  [ -n "$IRON_LINE" ]
  [ "$GEAR_LINE" -gt "$SKILL_LINE" ]
  [ "$GEAR_LINE" -lt "$IRON_LINE" ]
}

# ---------------------------------------------------------------------------
# (d) The gear block references the routing protocol file (a path, not a
#     slash-command) so the skill-ref canary stays green.
# ---------------------------------------------------------------------------

@test "gear-welcome: gear block references protocols/work-class-routing.md" {
  run _run_hook
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "protocols/work-class-routing.md"
}

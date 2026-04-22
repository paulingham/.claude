#!/usr/bin/env bats
# Integration: hooks now write/read state markers from $HOME/.claude/state/
# instead of /tmp/claude-*. Covers Cloud multi-session safety (H3).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP_HOME="$(mktemp -d)"
  # Symlink the real ~/.claude hooks dir into the fake $HOME so hooks that
  # source via `~/.claude/hooks/hook-profile.sh` still resolve, while the
  # state dir under $HOME/.claude/state is isolated.
  mkdir -p "$TMP_HOME/.claude"
  ln -s "$REPO_ROOT/hooks" "$TMP_HOME/.claude/hooks"
  export HOME="$TMP_HOME"
  export CLAUDE_STATE_DIR="$TMP_HOME/.claude/state"
  mkdir -p "$CLAUDE_STATE_DIR"
  export CLAUDE_HOOK_PROFILE="standard"
}

teardown() {
  rm -rf "$TMP_HOME"
  unset CLAUDE_STATE_DIR
}

@test "H3.5 observation-capture writes session id marker under state dir" {
  run bash -c "echo '{\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"/x\"},\"tool_output\":{}}' | bash '$REPO_ROOT/hooks/observation-capture.sh'"
  [ "$status" -eq 0 ]
  # One session-<pid> file should have been created in the state dir.
  count=$(find "$CLAUDE_STATE_DIR" -maxdepth 1 -name 'session-*' -type f | wc -l | tr -d ' ')
  [ "$count" -ge 1 ]
}

@test "H3.7 statusline writes ctx-percent to state dir" {
  # Statusline reads JSON on stdin with a context.used_percent field.
  run bash -c "echo '{\"workspace\":{\"current_dir\":\"$HOME\"},\"context\":{\"used_percent\":42}}' | bash '$REPO_ROOT/statusline-robbyrussell.sh' >/dev/null"
  [ "$status" -eq 0 ]
  [ -f "$CLAUDE_STATE_DIR/ctx-percent" ]
  [ "$(cat "$CLAUDE_STATE_DIR/ctx-percent")" = "42" ]
}

@test "H3.13 per-install isolation: two distinct \$HOMEs yield disjoint state dirs" {
  # Two "installs" (two HOME values) must never share a state file.
  install1="$TMP_HOME/install1"
  install2="$TMP_HOME/install2"
  mkdir -p "$install1/.claude/state" "$install2/.claude/state"
  HOME="$install1" CLAUDE_STATE_DIR="$install1/.claude/state" \
    bash -c "source '$REPO_ROOT/hooks/_lib/state-dir.sh'; echo hello-A > \"\$(_state_path test-marker)\""
  HOME="$install2" CLAUDE_STATE_DIR="$install2/.claude/state" \
    bash -c "source '$REPO_ROOT/hooks/_lib/state-dir.sh'; echo hello-B > \"\$(_state_path test-marker)\""
  [ "$(cat "$install1/.claude/state/test-marker")" = "hello-A" ]
  [ "$(cat "$install2/.claude/state/test-marker")" = "hello-B" ]
}

@test "H3.12 two concurrent shells write independent session markers (PID scoping)" {
  # Simulates two Cloud sessions sharing a host: each shell has a distinct PID,
  # so when it invokes observation-capture, the session-<PPID> markers must
  # be disjoint and readable from each shell.
  payload='{"tool_name":"Read","tool_input":{"file_path":"/x"},"tool_output":{}}'
  bash -c "echo '$payload' | bash '$REPO_ROOT/hooks/observation-capture.sh'; echo \$PPID" > "$TMP_HOME/p1.txt" &
  bg1=$!
  bash -c "echo '$payload' | bash '$REPO_ROOT/hooks/observation-capture.sh'; echo \$PPID" > "$TMP_HOME/p2.txt" &
  bg2=$!
  wait $bg1
  wait $bg2
  # Two distinct session-<pid> files must exist (no collision, no overwrite).
  count=$(find "$CLAUDE_STATE_DIR" -maxdepth 1 -name 'session-*' -type f | wc -l | tr -d ' ')
  [ "$count" -ge 2 ]
}

@test "H3.11 auto-bug-detect uses state dir for dedup (not /tmp)" {
  ! grep -q '/tmp/claude-hook-guard' "$REPO_ROOT/hooks/auto-bug-detect.sh"
  grep -q '_state_path' "$REPO_ROOT/hooks/auto-bug-detect.sh"
}

@test "H3.10 loop-guard uses state dir for hook-guard files" {
  run bash -c "source '$REPO_ROOT/hooks/loop-guard.sh'; source '$REPO_ROOT/hooks/_lib/state-dir.sh'; check_loop_guard 'probe' 10 60"
  [ "$status" -eq 0 ]
  [ -f "$CLAUDE_STATE_DIR/hook-guard/probe" ]
  ! grep -q '/tmp/claude-hook-guard' "$REPO_ROOT/hooks/loop-guard.sh"
}

@test "H3.9 subagent-context writes agent-role to state dir" {
  run bash -c "echo '{\"subagent_type\":\"software-engineer\"}' | bash '$REPO_ROOT/hooks/subagent-context.sh'"
  [ "$status" -eq 0 ]
  [ -f "$CLAUDE_STATE_DIR/agent-role" ]
  [ "$(cat "$CLAUDE_STATE_DIR/agent-role")" = "software-engineer" ]
}

@test "H3.8 cost-tracker reads session markers from state dir (not /tmp)" {
  # Seed a session id and start time under state dir for this PID.
  # PPID inside the hook is the subshell created by `bash -c`, so we probe
  # grep-level: the hook should source state-dir.sh and never touch /tmp.
  grep -q '_state_path' "$REPO_ROOT/hooks/cost-tracker.sh"
  ! grep -q '/tmp/claude-session' "$REPO_ROOT/hooks/cost-tracker.sh"
}

@test "H3.6 context-warning reads ctx-percent from state dir" {
  # Write a critical ctx-percent into the state dir; hook must emit the warning.
  echo "80" > "$CLAUDE_STATE_DIR/ctx-percent"
  # Seed the debounce counter so the very next call fires (mod-5 == 0).
  mkdir -p "$CLAUDE_STATE_DIR/hook-guard"
  echo "4" > "$CLAUDE_STATE_DIR/hook-guard/context-warning-count"
  run bash -c "echo '{}' | bash '$REPO_ROOT/hooks/context-warning.sh' 2>&1"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "CRITICAL CONTEXT WARNING"
}

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

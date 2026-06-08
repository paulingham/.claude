#!/usr/bin/env bats
# Integration: hooks now write/read state markers from $HOME/.claude/state/
# instead of /tmp/claude-*. Covers Cloud multi-session safety (H3).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  TMP_HOME="$(mktemp -d)"
  if [[ -n "${HOME+x}" ]]; then
    _PRIOR_HOME_SET=1; _PRIOR_HOME_VAL="$HOME"
  else
    _PRIOR_HOME_SET=0
  fi
  if [[ -n "${CLAUDE_STATE_DIR+x}" ]]; then
    _PRIOR_STATE_DIR_SET=1; _PRIOR_STATE_DIR_VAL="$CLAUDE_STATE_DIR"
  else
    _PRIOR_STATE_DIR_SET=0
  fi
  if [[ -n "${CLAUDE_HOOK_PROFILE+x}" ]]; then
    _PRIOR_HOOK_PROFILE_SET=1; _PRIOR_HOOK_PROFILE_VAL="$CLAUDE_HOOK_PROFILE"
  else
    _PRIOR_HOOK_PROFILE_SET=0
  fi
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
  if [[ "$_PRIOR_HOME_SET" = "1" ]]; then
    export HOME="$_PRIOR_HOME_VAL"
  else
    unset HOME
  fi
  if [[ "$_PRIOR_STATE_DIR_SET" = "1" ]]; then
    export CLAUDE_STATE_DIR="$_PRIOR_STATE_DIR_VAL"
  else
    unset CLAUDE_STATE_DIR
  fi
  if [[ "$_PRIOR_HOOK_PROFILE_SET" = "1" ]]; then
    export CLAUDE_HOOK_PROFILE="$_PRIOR_HOOK_PROFILE_VAL"
  else
    unset CLAUDE_HOOK_PROFILE
  fi
}

_stat_mode() {
  # Linux (stat -c) first; macOS (stat -f) fallback. `stat -f` on Linux does
  # NOT fail cleanly (it means filesystem), so it must not be tried first.
  stat -c %a "$1" 2>/dev/null || stat -f %A "$1"
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
  # Writes ctx-percent-${PPID} for per-session isolation within an install.
  run bash -c "echo '{\"workspace\":{\"current_dir\":\"$HOME\"},\"context\":{\"used_percent\":42}}' | bash '$REPO_ROOT/statusline-robbyrussell.sh' >/dev/null"
  [ "$status" -eq 0 ]
  ctx_file=$(find "$CLAUDE_STATE_DIR" -maxdepth 1 -name 'ctx-percent-*' -type f | head -1)
  [ -n "$ctx_file" ]
  [ "$(cat "$ctx_file")" = "42" ]
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
  # Within-install per-session PID scoping (combined with H3.13 for cross-install
  # isolation). Each shell has a distinct PID, so when it invokes
  # observation-capture, the session-<PPID> markers must be disjoint and
  # readable from each shell. H3.13 covers the orthogonal case: two installs
  # on one host must not share a state directory at all.
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
  # Writes agent-role-${PPID} for per-session isolation within an install.
  run bash -c "echo '{\"subagent_type\":\"software-engineer\"}' | bash '$REPO_ROOT/hooks/subagent-context.sh'"
  [ "$status" -eq 0 ]
  role_file=$(find "$CLAUDE_STATE_DIR" -maxdepth 1 -name 'agent-role-*' -type f | head -1)
  [ -n "$role_file" ]
  [ "$(cat "$role_file")" = "software-engineer" ]
}

@test "H3.8 cost-tracker reads session markers from state dir (not /tmp)" {
  # Seed a session id and start time under state dir for this PID.
  # PPID inside the hook is the subshell created by `bash -c`, so we probe
  # grep-level: the hook should source state-dir.sh and never touch /tmp.
  grep -q '_state_path' "$REPO_ROOT/hooks/cost-tracker.sh"
  ! grep -q '/tmp/claude-session' "$REPO_ROOT/hooks/cost-tracker.sh"
}

@test "H3.6 context-warning reads ctx-percent from state dir" {
  # Writes ctx-percent-${PPID} into state dir; hook must emit the warning.
  # Keying by the subshell PID the hook will see ($$ in the bash -c subshell).
  run bash -c '
    pid_proxy=$$
    echo "80" > "$CLAUDE_STATE_DIR/ctx-percent-$pid_proxy"
    mkdir -p "$CLAUDE_STATE_DIR/hook-guard"
    echo "4" > "$CLAUDE_STATE_DIR/hook-guard/context-warning-count"
    echo "{}" | bash "'"$REPO_ROOT"'/hooks/context-warning.sh" 2>&1
  '
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "CRITICAL CONTEXT WARNING"
}

@test "H3.14 observation-capture writes session marker with mode 0600" {
  run bash -c "echo '{\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"/x\"},\"tool_output\":{}}' | bash '$REPO_ROOT/hooks/observation-capture.sh'"
  [ "$status" -eq 0 ]
  marker=$(find "$CLAUDE_STATE_DIR" -maxdepth 1 -name 'session-*' -type f | head -1)
  [ -n "$marker" ]
  mode=$(_stat_mode "$marker")
  [ "$mode" = "600" ]
}

@test "H3.15 subagent-context writes agent-role with mode 0600" {
  run bash -c "echo '{\"subagent_type\":\"software-engineer\"}' | bash '$REPO_ROOT/hooks/subagent-context.sh'"
  [ "$status" -eq 0 ]
  role_file=$(find "$CLAUDE_STATE_DIR" -maxdepth 1 -name 'agent-role*' -type f | head -1)
  [ -n "$role_file" ]
  mode=$(_stat_mode "$role_file")
  [ "$mode" = "600" ]
}

@test "H3.16 statusline writes ctx-percent with mode 0600" {
  run bash -c "echo '{\"workspace\":{\"current_dir\":\"$HOME\"},\"context\":{\"used_percent\":42}}' | bash '$REPO_ROOT/statusline-robbyrussell.sh' >/dev/null"
  [ "$status" -eq 0 ]
  ctx_file=$(find "$CLAUDE_STATE_DIR" -maxdepth 1 -name 'ctx-percent*' -type f | head -1)
  [ -n "$ctx_file" ]
  mode=$(_stat_mode "$ctx_file")
  [ "$mode" = "600" ]
}

@test "H3.17 statusline scopes ctx-percent by PPID (two sessions on one host do not collide)" {
  # Simulate two Claude Code processes writing different ctx percentages
  # concurrently. Each writer's PPID is unique, so there must be two files.
  bash -c "echo '{\"workspace\":{\"current_dir\":\"$HOME\"},\"context\":{\"used_percent\":25}}' | bash '$REPO_ROOT/statusline-robbyrussell.sh' >/dev/null" &
  bg1=$!
  bash -c "echo '{\"workspace\":{\"current_dir\":\"$HOME\"},\"context\":{\"used_percent\":70}}' | bash '$REPO_ROOT/statusline-robbyrussell.sh' >/dev/null" &
  bg2=$!
  wait $bg1
  wait $bg2
  count=$(find "$CLAUDE_STATE_DIR" -maxdepth 1 -name 'ctx-percent-*' -type f | wc -l | tr -d ' ')
  [ "$count" -ge 2 ]
}

@test "H3.18 subagent-context scopes agent-role by PPID (two orchestrators do not collide)" {
  bash -c "echo '{\"subagent_type\":\"software-engineer\"}' | bash '$REPO_ROOT/hooks/subagent-context.sh'" &
  bg1=$!
  bash -c "echo '{\"subagent_type\":\"code-reviewer\"}' | bash '$REPO_ROOT/hooks/subagent-context.sh'" &
  bg2=$!
  wait $bg1
  wait $bg2
  count=$(find "$CLAUDE_STATE_DIR" -maxdepth 1 -name 'agent-role-*' -type f | wc -l | tr -d ' ')
  [ "$count" -ge 2 ]
}

@test "H3.19 context-warning reads ctx-percent-\${PPID} (PPID-scoped)" {
  # Write ctx-percent keyed by the subshell PID the hook will see.
  run bash -c '
    pid_proxy=$$
    mkdir -p "$CLAUDE_STATE_DIR/hook-guard"
    echo "80" > "$CLAUDE_STATE_DIR/ctx-percent-$pid_proxy"
    echo "4" > "$CLAUDE_STATE_DIR/hook-guard/context-warning-count"
    echo "{}" | bash "'"$REPO_ROOT"'/hooks/context-warning.sh" 2>&1
  '
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "CRITICAL CONTEXT WARNING"
}

@test "H3.20 observation-capture reads agent-role-\${PPID} (PPID-scoped)" {
  # Write agent-role keyed by the subshell PID the hook will see.
  run bash -c '
    pid_proxy=$$
    echo "code-reviewer" > "$CLAUDE_STATE_DIR/agent-role-$pid_proxy"
    echo "{\"tool_name\":\"Read\",\"tool_input\":{\"file_path\":\"/x\"},\"tool_output\":{}}" | \
      CLAUDE_SESSION_ID=test-ppid-scope \
      bash "'"$REPO_ROOT"'/hooks/observation-capture.sh" 2>/dev/null
  '
  [ "$status" -eq 0 ]
  # Find the observations jsonl the hook wrote to
  obs_file=$(find "$HOME/.claude/learning" -name observations.jsonl -type f | head -1)
  [ -n "$obs_file" ]
  role=$(tail -1 "$obs_file" | jq -r '.agent_role // empty')
  [ "$role" = "code-reviewer" ]
}

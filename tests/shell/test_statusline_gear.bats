#!/usr/bin/env bats
# Statusline gear segment (Phase A). The statusline reads gear-${PPID} from
# state-dir (written by hooks/_lib/gear-select.sh) and appends a colored
# " ⚙ PAIR|BUILD|PIPELINE" segment. Additive/no-op when no gear marker
# exists — must never break the existing statusline output.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  STATUSLINE="$REPO_ROOT/statusline-robbyrussell.sh"
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
  mkdir -p "$TMP_HOME/.claude"
  ln -s "$REPO_ROOT/hooks" "$TMP_HOME/.claude/hooks"
  export HOME="$TMP_HOME"
  export CLAUDE_STATE_DIR="$TMP_HOME/.claude/state"
  mkdir -p "$CLAUDE_STATE_DIR"
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
}

@test "SL1.1 statusline appends the PAIR gear segment when gear-\${PPID} is PAIR" {
  run bash -c '
    pid_proxy=$$
    echo "PAIR" > "$CLAUDE_STATE_DIR/gear-$pid_proxy"
    echo "{\"workspace\":{\"current_dir\":\"'"$HOME"'\"}}" | bash "'"$STATUSLINE"'"
  '
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '⚙ PAIR'
}

@test "SL1.2 statusline appends the BUILD gear segment when gear-\${PPID} is BUILD" {
  run bash -c '
    pid_proxy=$$
    echo "BUILD" > "$CLAUDE_STATE_DIR/gear-$pid_proxy"
    echo "{\"workspace\":{\"current_dir\":\"'"$HOME"'\"}}" | bash "'"$STATUSLINE"'"
  '
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '⚙ BUILD'
}

@test "SL1.3 statusline appends the PIPELINE gear segment when gear-\${PPID} is PIPELINE" {
  run bash -c '
    pid_proxy=$$
    echo "PIPELINE" > "$CLAUDE_STATE_DIR/gear-$pid_proxy"
    echo "{\"workspace\":{\"current_dir\":\"'"$HOME"'\"}}" | bash "'"$STATUSLINE"'"
  '
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '⚙ PIPELINE'
}

@test "SL1.4 statusline renders no gear segment when no gear marker exists (additive no-op)" {
  run bash -c "echo '{\"workspace\":{\"current_dir\":\"$HOME\"}}' | bash '$STATUSLINE'"
  [ "$status" -eq 0 ]
  ! echo "$output" | grep -q '⚙'
}

@test "SL1.5 statusline still renders the current directory segment (does not break existing output)" {
  run bash -c "echo '{\"workspace\":{\"current_dir\":\"$HOME\"}}' | bash '$STATUSLINE'"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "$(basename "$HOME")"
}

@test "SL1.6 statusline gear segment is scoped by PPID (two sessions do not collide)" {
  bash -c '
    pid_proxy=$$
    echo "PAIR" > "$CLAUDE_STATE_DIR/gear-$pid_proxy"
    echo "{\"workspace\":{\"current_dir\":\"'"$HOME"'\"}}" | bash "'"$STATUSLINE"'" > "'"$TMP_HOME"'/out1.txt"
  ' &
  bg1=$!
  bash -c '
    pid_proxy=$$
    echo "PIPELINE" > "$CLAUDE_STATE_DIR/gear-$pid_proxy"
    echo "{\"workspace\":{\"current_dir\":\"'"$HOME"'\"}}" | bash "'"$STATUSLINE"'" > "'"$TMP_HOME"'/out2.txt"
  ' &
  bg2=$!
  wait $bg1
  wait $bg2
  grep -q '⚙ PAIR' "$TMP_HOME/out1.txt"
  grep -q '⚙ PIPELINE' "$TMP_HOME/out2.txt"
}

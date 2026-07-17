#!/usr/bin/env bats
# Statusline gear segment (Phase A/B). The statusline reads gear-${sid} from
# state-dir (written by hooks/_lib/gear-select.sh, keyed by session_id — see
# hooks/_lib/gear-gate.sh header for why PPID cannot round-trip across the
# separate processes that write vs. read gear state) and appends a colored
# " ⚙ PAIR|BUILD|PIPELINE" segment. Additive/no-op when no gear marker
# exists — must never break the existing statusline output.
#
# ctx-percent-${PPID} (a separate, unrelated bridge) intentionally stays
# PPID-keyed in this change — only the gear segment moves to session id.

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

@test "SL1.1 statusline appends the PAIR gear segment when gear-<sid> is PAIR" {
  printf 'PAIR\n' > "$CLAUDE_STATE_DIR/gear-sess-1"
  run bash -c "printf '{\"workspace\":{\"current_dir\":\"%s\"},\"session_id\":\"sess-1\"}' \"\$1\" | bash \"\$2\"" _ "$HOME" "$STATUSLINE"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '⚙ PAIR'
}

@test "SL1.2 statusline appends the BUILD gear segment when gear-<sid> is BUILD" {
  printf 'BUILD\n' > "$CLAUDE_STATE_DIR/gear-sess-1"
  run bash -c "printf '{\"workspace\":{\"current_dir\":\"%s\"},\"session_id\":\"sess-1\"}' \"\$1\" | bash \"\$2\"" _ "$HOME" "$STATUSLINE"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '⚙ BUILD'
}

@test "SL1.3 statusline appends the PIPELINE gear segment when gear-<sid> is PIPELINE" {
  printf 'PIPELINE\n' > "$CLAUDE_STATE_DIR/gear-sess-1"
  run bash -c "printf '{\"workspace\":{\"current_dir\":\"%s\"},\"session_id\":\"sess-1\"}' \"\$1\" | bash \"\$2\"" _ "$HOME" "$STATUSLINE"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '⚙ PIPELINE'
}

@test "SL1.4 statusline renders no gear segment when no gear marker exists (additive no-op)" {
  run bash -c "printf '{\"workspace\":{\"current_dir\":\"%s\"},\"session_id\":\"sess-never-written\"}' \"\$1\" | bash \"\$2\"" _ "$HOME" "$STATUSLINE"
  [ "$status" -eq 0 ]
  ! echo "$output" | grep -q '⚙'
}

@test "SL1.5 statusline still renders the current directory segment (does not break existing output)" {
  run bash -c "printf '{\"workspace\":{\"current_dir\":\"%s\"}}' \"\$1\" | bash \"\$2\"" _ "$HOME" "$STATUSLINE"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "$(basename "$HOME")"
}

@test "SL1.6 statusline gear segment is scoped by session_id (two sessions do not collide)" {
  printf 'PAIR\n' > "$CLAUDE_STATE_DIR/gear-sess-a"
  printf 'PIPELINE\n' > "$CLAUDE_STATE_DIR/gear-sess-b"
  bash -c "printf '{\"workspace\":{\"current_dir\":\"%s\"},\"session_id\":\"sess-a\"}' \"\$1\" | bash \"\$2\" > \"\$3/out1.txt\"" _ "$HOME" "$STATUSLINE" "$TMP_HOME" &
  bg1=$!
  bash -c "printf '{\"workspace\":{\"current_dir\":\"%s\"},\"session_id\":\"sess-b\"}' \"\$1\" | bash \"\$2\" > \"\$3/out2.txt\"" _ "$HOME" "$STATUSLINE" "$TMP_HOME" &
  bg2=$!
  wait $bg1
  wait $bg2
  grep -q '⚙ PAIR' "$TMP_HOME/out1.txt"
  grep -q '⚙ PIPELINE' "$TMP_HOME/out2.txt"
}

# ---------------------------------------------------------------------------
# Cross-process — the real production condition. gear-select.sh writes
# gear-<sid> from a SEPARATE process (simulating UserPromptSubmit); the
# statusline reads it from its OWN separate process (a different PID/PPID
# entirely), keyed by the SAME session_id carried in ITS OWN stdin payload.
# ---------------------------------------------------------------------------

@test "CP1 cross-process: gear-select writes under stdin session_id, a SEPARATE statusline invocation reads it via its own stdin session_id" {
  run bash -c "source '$REPO_ROOT/hooks/_lib/gear-select.sh'; printf '{\"prompt\": \"just pair on this\", \"session_id\": \"sess-xproc-sl\"}' | gear_select"
  [ "$status" -eq 0 ]
  [ "$output" = "PAIR" ]

  run bash -c "printf '{\"workspace\":{\"current_dir\":\"%s\"},\"session_id\":\"sess-xproc-sl\"}' \"\$1\" | bash \"\$2\"" _ "$HOME" "$STATUSLINE"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '⚙ PAIR'
}

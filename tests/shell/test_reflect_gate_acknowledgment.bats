#!/usr/bin/env bats
# Phase B WS2 — gear-gate for hooks/reflect-gate-acknowledgment.sh: this gate
# only has meaning in the Pipeline gear (Reflect is a Pipeline-only phase).
# No-op (exit 0, silent) in PAIR even when unacknowledged tokens exist.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/reflect-gate-acknowledgment.sh"
  TMP="$(mktemp -d -t rga.XXXXXX)"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_PLUGIN_DATA="$TMP/harness-data"
  export CLAUDE_STATE_DIR="$TMP/state"
  export CLAUDE_SESSION_ID="test-session-$$"
  TOKEN_DIR="$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID/reflect-tokens"
  mkdir -p "$TOKEN_DIR"
  mkdir -p "$CLAUDE_STATE_DIR"
  # An unacknowledged token — the condition that should BLOCK when the gate
  # is actually evaluated (non-PAIR gears).
  printf '{"deviation_id":"d1","acknowledged":false}' > "$TOKEN_DIR/d1.json"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_run_hook_with_gear() {
  local gear="$1"; shift
  printf '%s\n' "$gear" > "$CLAUDE_STATE_DIR/gear-${CLAUDE_SESSION_ID}"
  run "$HOOK" "$@"
}

@test "baseline: unacknowledged token blocks (exit 1) with no gear state" {
  run "$HOOK"
  [ "$status" -eq 1 ]
}

@test "GG1 gear=PAIR -> hook no-ops (exit 0) even with an unacknowledged token" {
  _run_hook_with_gear "PAIR"
  [ "$status" -eq 0 ]
}

@test "GG2 gear=BUILD -> hook still blocks (exit 1) on the unacknowledged token" {
  _run_hook_with_gear "BUILD"
  [ "$status" -eq 1 ]
}

@test "GG3 gear=PIPELINE -> hook still blocks (exit 1) on the unacknowledged token" {
  _run_hook_with_gear "PIPELINE"
  [ "$status" -eq 1 ]
}

@test "GG4 gear state absent -> hook still blocks (exit 1, fail-safe)" {
  run "$HOOK"
  [ "$status" -eq 1 ]
}

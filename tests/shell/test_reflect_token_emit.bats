#!/usr/bin/env bats
# Phase B WS2 — gear-gate for hooks/reflect-token-emit.sh: this hook records
# Reflect-phase named-deviation tokens, which only exist in the Pipeline
# gear (Reflect is a Pipeline-only phase per rules/core.md). No-op in PAIR.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/reflect-token-emit.sh"
  TMP="$(mktemp -d -t rte.XXXXXX)"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_PLUGIN_DATA="$TMP/harness-data"
  export CLAUDE_STATE_DIR="$TMP/state"
  export CLAUDE_SESSION_ID="test-session-$$"
  mkdir -p "$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID"
  mkdir -p "$CLAUDE_STATE_DIR"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_token_path() {
  printf '%s' "$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID/reflect-tokens/some-deviation.json"
}

# Fixture writes gear-<CLAUDE_SESSION_ID> directly — the hook resolves its
# own sid via resolve_session_id(""), which falls back to $CLAUDE_SESSION_ID
# (pinned to a known value in setup()).
_run_hook_with_gear() {
  local gear="$1"; shift
  printf '%s\n' "$gear" > "$CLAUDE_STATE_DIR/gear-${CLAUDE_SESSION_ID}"
  run "$HOOK" "$@"
}

@test "baseline: default (no gear state) writes a reflect token" {
  run "$HOOK" "some-deviation"
  [ "$status" -eq 0 ]
  [ -f "$(_token_path)" ]
}

@test "GG1 gear=PAIR -> hook no-ops (exit 0, no token file written)" {
  _run_hook_with_gear "PAIR" "some-deviation"
  [ "$status" -eq 0 ]
  [ ! -f "$(_token_path)" ]
}

@test "GG2 gear=BUILD -> hook runs its logic (token file written)" {
  _run_hook_with_gear "BUILD" "some-deviation"
  [ "$status" -eq 0 ]
  [ -f "$(_token_path)" ]
}

@test "GG3 gear=PIPELINE -> hook runs its logic (token file written)" {
  _run_hook_with_gear "PIPELINE" "some-deviation"
  [ "$status" -eq 0 ]
  [ -f "$(_token_path)" ]
}

@test "GG4 gear state absent -> hook runs its logic (fail-safe, token file written)" {
  run "$HOOK" "some-deviation"
  [ "$status" -eq 0 ]
  [ -f "$(_token_path)" ]
}

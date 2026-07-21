#!/usr/bin/env bats
# gear-announce.sh — UserPromptSubmit announce hook that surfaces the per-turn
# gear classification (PAIR/BUILD/PIPELINE) to the USER as a visible one-line
# systemMessage banner. It reads the gear that gear-select.sh already persisted
# to session state; it never re-classifies. ADVISORY: exit 0 always (an announce
# hook must never block a prompt) and stay SILENT when the gear is unconfirmable.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/gear-announce.sh"
  TMP_STATE="$(mktemp -d -t gear-announce-state.XXXXXX)"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_CONFIG_DIR="$REPO_ROOT"
  export CLAUDE_STATE_DIR="$TMP_STATE"
  SID="sess-ga-test"
  PAYLOAD='{"prompt":"hello","session_id":"sess-ga-test"}'
}

teardown() {
  rm -rf "$TMP_STATE"
}

# Writes a gear fixture into session state, then runs the hook with $PAYLOAD
# piped in. When $1 is empty, no fixture is written (fresh/absent-state case).
_run_hook_with_gear() {
  local gear="$1"
  [[ -n "$gear" ]] && printf '%s\n' "$gear" > "$TMP_STATE/gear-${SID}"
  run bash -c 'printf "%s" "$1" | bash "$2"' _ "$PAYLOAD" "$HOOK"
}

@test "gear=PAIR -> systemMessage announces PAIR, exit 0" {
  _run_hook_with_gear "PAIR"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"systemMessage"'* ]]
  [[ "$output" == *"PAIR"* ]]
}

@test "gear=BUILD -> systemMessage announces BUILD, exit 0" {
  _run_hook_with_gear "BUILD"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"systemMessage"'* ]]
  [[ "$output" == *"BUILD"* ]]
}

@test "gear=PIPELINE -> systemMessage announces PIPELINE, exit 0" {
  _run_hook_with_gear "PIPELINE"
  [ "$status" -eq 0 ]
  [[ "$output" == *'"systemMessage"'* ]]
  [[ "$output" == *"PIPELINE"* ]]
}

@test "no gear state present -> clean no-op: exit 0, no systemMessage" {
  _run_hook_with_gear ""
  [ "$status" -eq 0 ]
  [[ "$output" != *"systemMessage"* ]]
}

@test "unknown gear value in state -> silent no-op (never announce unconfirmed gear)" {
  _run_hook_with_gear "GARBAGE"
  [ "$status" -eq 0 ]
  [[ "$output" != *"systemMessage"* ]]
}

@test "emitted output is valid JSON (does not corrupt the hook channel)" {
  _run_hook_with_gear "PAIR"
  [ "$status" -eq 0 ]
  echo "$output" | python3 -m json.tool >/dev/null
}

@test "malformed stdin JSON -> exit 0 (announce hook never blocks a prompt)" {
  run bash -c 'printf "%s" "$1" | bash "$2"' _ 'not-json-at-all' "$HOOK"
  [ "$status" -eq 0 ]
}

@test "empty stdin -> exit 0 (announce hook never blocks a prompt)" {
  run bash -c 'printf "%s" "" | bash "$1"' _ "$HOOK"
  [ "$status" -eq 0 ]
}

#!/usr/bin/env bats
# Gear-gate for hooks/block-ask-user.sh: AskUserQuestion is blocked in
# autonomous Build/Pipeline gear work, but ALLOWED in PAIR gear where
# interactive questions are the whole point. Fail-closed (block) when gear
# state is absent/unreadable. The gear fixture is keyed on the payload's
# .session_id, resolved by the hook via resolve_session_id.
#
# "hook ran" == exit 2 (BLOCKED); "hook no-opped" == exit 0 (ALLOWED).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/block-ask-user.sh"
  TMP_STATE="$(mktemp -d -t bau-state.XXXXXX)"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_CONFIG_DIR="$REPO_ROOT"
  export CLAUDE_STATE_DIR="$TMP_STATE"
  SID="sess-bau-test"
  PAYLOAD='{"tool_name":"AskUserQuestion","session_id":"'"$SID"'","cwd":"/tmp"}'
}

teardown() {
  rm -rf "$TMP_STATE"
}

_run_hook_with_gear() {
  local gear="$1"
  printf '%s\n' "$gear" > "$TMP_STATE/gear-${SID}"
  run bash -c 'printf "%s" "$1" | bash "$2"' _ "$PAYLOAD" "$HOOK"
}

@test "baseline: AskUserQuestion blocks (exit 2) with no gear state (fail-closed)" {
  run bash -c 'printf "%s" "$1" | bash "$2"' _ "$PAYLOAD" "$HOOK"
  [ "$status" -eq 2 ]
}

@test "GG1 gear=PAIR -> AskUserQuestion allowed (exit 0)" {
  _run_hook_with_gear "PAIR"
  [ "$status" -eq 0 ]
}

@test "GG2 gear=BUILD -> AskUserQuestion blocked (exit 2)" {
  _run_hook_with_gear "BUILD"
  [ "$status" -eq 2 ]
}

@test "GG3 gear=PIPELINE -> AskUserQuestion blocked (exit 2)" {
  _run_hook_with_gear "PIPELINE"
  [ "$status" -eq 2 ]
}

@test "GG4 gear state absent -> AskUserQuestion blocked (exit 2, fail-closed)" {
  run bash -c 'printf "%s" "$1" | bash "$2"' _ "$PAYLOAD" "$HOOK"
  [ "$status" -eq 2 ]
}

@test "GG5 non-AskUserQuestion tool (Read) with gear=BUILD -> no-op (exit 0)" {
  local read_payload='{"tool_name":"Read","session_id":"'"$SID"'","cwd":"/tmp"}'
  printf '%s\n' "BUILD" > "$TMP_STATE/gear-${SID}"
  run bash -c 'printf "%s" "$1" | bash "$2"' _ "$read_payload" "$HOOK"
  [ "$status" -eq 0 ]
}

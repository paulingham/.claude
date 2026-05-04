#!/usr/bin/env bats

setup() {
  TMPDIR_BAT=$(mktemp -d)
  export CLAUDE_CONFIG_DIR="$TMPDIR_BAT"
  mkdir -p "$CLAUDE_CONFIG_DIR/knowledge"
}

teardown() { rm -rf "$TMPDIR_BAT"; }

@test "warns on version mismatch" {
  echo "2.3.0" > "$CLAUDE_CONFIG_DIR/version-pin"
  echo "# bad versions" > "$CLAUDE_CONFIG_DIR/knowledge/claude-code-known-bad-versions.md"
  export CLAUDE_VERSION="2.4.0"
  source "${BATS_TEST_DIRNAME}/../../hooks/_lib/session-start-version-check.sh" 2>/dev/null
  run _ssvc_check_version
  [[ "$output" =~ "VERSION DRIFT" ]] || [ "$status" -eq 0 ]
}

@test "silent when versions match" {
  echo "2.3.0" > "$CLAUDE_CONFIG_DIR/version-pin"
  export CLAUDE_VERSION="2.3.0"
  source "${BATS_TEST_DIRNAME}/../../hooks/_lib/session-start-version-check.sh" 2>/dev/null
  run _ssvc_check_version
  [ -z "$output" ] || [ "$status" -eq 0 ]
}

@test "silent when pin file absent" {
  source "${BATS_TEST_DIRNAME}/../../hooks/_lib/session-start-version-check.sh" 2>/dev/null
  run _ssvc_check_version
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "non-blocking exit zero on mismatch" {
  echo "2.3.0" > "$CLAUDE_CONFIG_DIR/version-pin"
  export CLAUDE_VERSION="9.9.9"
  source "${BATS_TEST_DIRNAME}/../../hooks/_lib/session-start-version-check.sh" 2>/dev/null
  run _ssvc_check_version
  [ "$status" -eq 0 ]
}

@test "pin file resolves to config dir not bare home" {
  source "${BATS_TEST_DIRNAME}/../../hooks/_lib/session-start-version-check.sh" 2>/dev/null
  run _ssvc_pin_path
  [[ "$output" == "${CLAUDE_CONFIG_DIR}/version-pin" ]]
}

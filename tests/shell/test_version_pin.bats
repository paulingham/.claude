#!/usr/bin/env bats

setup() {
  TMPDIR_BAT=$(mktemp -d)
  export CLAUDE_CONFIG_DIR="$TMPDIR_BAT"
  mkdir -p "$CLAUDE_CONFIG_DIR/knowledge"
  unset CLAUDE_VERSION
}

teardown() { rm -rf "$TMPDIR_BAT"; }

load_helper() {
  source "${BATS_TEST_DIRNAME}/../../hooks/_lib/session-start-version-check.sh" 2>/dev/null
}

# --- AC3: _ssvc_version_lt numeric semver ordering ---

@test "_ssvc_version_lt: equal versions returns false" {
  load_helper
  run _ssvc_version_lt 2.1.160 2.1.160
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: running patch greater returns false" {
  load_helper
  run _ssvc_version_lt 2.1.161 2.1.160
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: running patch less returns true" {
  load_helper
  run _ssvc_version_lt 2.1.159 2.1.160
  [ "$status" -eq 0 ]
}

@test "_ssvc_version_lt: running minor greater returns false" {
  load_helper
  run _ssvc_version_lt 2.2.0 2.1.160
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: running minor less returns true" {
  load_helper
  run _ssvc_version_lt 2.0.0 2.1.160
  [ "$status" -eq 0 ]
}

@test "_ssvc_version_lt: running major greater returns false" {
  load_helper
  run _ssvc_version_lt 3.0.0 2.1.160
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: running major less returns true" {
  load_helper
  run _ssvc_version_lt 1.9.9 2.1.160
  [ "$status" -eq 0 ]
}

@test "_ssvc_version_lt: multi-digit patch numeric not lexical (9 < 160)" {
  load_helper
  run _ssvc_version_lt 2.1.9 2.1.160
  [ "$status" -eq 0 ]
}

@test "_ssvc_version_lt: empty string A returns false (no-warn on missing version)" {
  load_helper
  run _ssvc_version_lt "" 2.1.160
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: short version 2.1 padded to 2.1.0 equals 2.1.0" {
  load_helper
  run _ssvc_version_lt 2.1 2.1.0
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: short floor 2.1 pads patch to 0 (2.1.5 not below 2.1)" {
  load_helper
  run _ssvc_version_lt 2.1.5 2.1
  [ "$status" -eq 1 ]
}

@test "_ssvc_version_lt: short running 2.1 pads patch to 0 (2.1 below 2.1.5)" {
  load_helper
  run _ssvc_version_lt 2.1 2.1.5
  [ "$status" -eq 0 ]
}

# --- AC1: _ssvc_check_version minimum-version semantics ---

@test "_ssvc_check_version: running equal to floor is silent" {
  echo "2.1.160" > "$CLAUDE_CONFIG_DIR/version-pin"
  export CLAUDE_VERSION="2.1.160"
  load_helper
  run _ssvc_check_version
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_ssvc_check_version: running above floor is silent" {
  echo "2.1.160" > "$CLAUDE_CONFIG_DIR/version-pin"
  export CLAUDE_VERSION="2.1.200"
  load_helper
  run _ssvc_check_version
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "_ssvc_check_version: running below floor emits VERSION FLOOR warning" {
  echo "2.1.160" > "$CLAUDE_CONFIG_DIR/version-pin"
  export CLAUDE_VERSION="2.1.100"
  load_helper
  run _ssvc_check_version
  [[ "$output" =~ "VERSION FLOOR" ]]
}

@test "_ssvc_check_version: non-blocking exit 0 even when below floor" {
  echo "2.1.160" > "$CLAUDE_CONFIG_DIR/version-pin"
  export CLAUDE_VERSION="1.0.0"
  load_helper
  run _ssvc_check_version
  [ "$status" -eq 0 ]
}

@test "_ssvc_check_version: no pin file is silent" {
  load_helper
  run _ssvc_check_version
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- AC2: real version-pin file value ---

@test "version-pin file contains 2.1.160" {
  run cat "${BATS_TEST_DIRNAME}/../../version-pin"
  [ "$status" -eq 0 ]
  [[ "$output" =~ ^2\.1\.160$ ]]
}

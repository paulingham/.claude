#!/usr/bin/env bats
# Specs for scripts/_lib/install-rtk.sh
# Hermetic: CLAUDE_RTK_HAS_RTK, CLAUDE_RTK_PRINTER, CLAUDE_RTK_FORCE_CURL_FAIL,
# CLAUDE_RTK_FORCE_CARGO_FAIL, INSTALL_PKG_CMD_PRINTER.
# Zero network access — PRINTER short-circuits before any real command runs.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  TMP_DIR="$(mktemp -d)"
}

teardown() {
  rm -rf "$TMP_DIR"
}

# Helper: create a brew stub in TMP_DIR/bin
_make_brew_stub() {
  mkdir -p "$TMP_DIR/bin"
  printf '#!/bin/sh\necho "Homebrew 4.0"\n' > "$TMP_DIR/bin/brew"
  chmod +x "$TMP_DIR/bin/brew"
}

# Helper: create a cargo stub in TMP_DIR/bin
_make_cargo_stub() {
  mkdir -p "$TMP_DIR/bin"
  printf '#!/bin/sh\necho "cargo 1.0"\n' > "$TMP_DIR/bin/cargo"
  chmod +x "$TMP_DIR/bin/cargo"
}

# ---------- idempotency ----------

@test "install_rtk: rtk already present -> no-op (no PRINTER output)" {
  run bash -c "export CLAUDE_RTK_HAS_RTK=1; export CLAUDE_RTK_PRINTER=echo; source '$LIB_DIR/install-rtk.sh'; install_rtk macos"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---------- default path: curl installer, not brew ----------

@test "install_rtk: default path emits curl installer, not brew" {
  run bash -c "export CLAUDE_RTK_PRINTER=echo; export PATH='/nowhere:/usr/bin:/bin'; source '$LIB_DIR/install-rtk.sh'; install_rtk macos"
  [ "$status" -eq 0 ]
  [[ "$output" == *"curl"* ]]
  [[ "$output" != *"brew"* ]]
}

# ---------- FORCE_CURL_FAIL -> cargo ----------

@test "install_rtk: FORCE_CURL_FAIL -> emits cargo install --git" {
  _make_cargo_stub
  run bash -c "export CLAUDE_RTK_PRINTER=echo; export CLAUDE_RTK_FORCE_CURL_FAIL=1; export PATH='$TMP_DIR/bin:/usr/bin:/bin'; source '$LIB_DIR/install-rtk.sh'; install_rtk macos"
  [ "$status" -eq 0 ]
  [[ "$output" == *"cargo"* ]]
  [[ "$output" == *"--git"* ]]
}

# ---------- FORCE_CURL_FAIL + FORCE_CARGO_FAIL + brew -> brew last-resort ----------

@test "install_rtk: FORCE_CURL_FAIL + FORCE_CARGO_FAIL + brew stub -> emits brew install rtk" {
  _make_brew_stub
  run bash -c "export CLAUDE_RTK_PRINTER=echo; export CLAUDE_RTK_FORCE_CURL_FAIL=1; export CLAUDE_RTK_FORCE_CARGO_FAIL=1; export PATH='$TMP_DIR/bin:/usr/bin:/bin'; source '$LIB_DIR/install-rtk.sh'; install_rtk macos"
  [ "$status" -eq 0 ]
  [[ "$output" == *"brew"* ]]
  [[ "$output" == *"rtk"* ]]
}

# ---------- all methods fail -> rc 1 ----------

@test "install_rtk: FORCE_CURL_FAIL + FORCE_CARGO_FAIL + no brew -> returns non-zero" {
  run bash -c "export CLAUDE_RTK_FORCE_CURL_FAIL=1; export CLAUDE_RTK_FORCE_CARGO_FAIL=1; export PATH='/nowhere:/usr/bin:/bin'; source '$LIB_DIR/install-rtk.sh'; install_rtk macos"
  [ "$status" -ne 0 ]
}

# ---------- no-brew invariant on default path ----------

@test "install_rtk: macos -> no brew token in default path (no-brew invariant)" {
  run bash -c "export CLAUDE_RTK_PRINTER=echo; export PATH='/nowhere:/usr/bin:/bin'; source '$LIB_DIR/install-rtk.sh'; install_rtk macos"
  [ "$status" -eq 0 ]
  [[ "$output" != *"brew"* ]]
}

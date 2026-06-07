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

# ---------- FORCE_CURL_FAIL + FORCE_CARGO_FAIL + brew -> brew last-resort (macOS only) ----------

@test "install_rtk: FORCE_CURL_FAIL + FORCE_CARGO_FAIL + brew stub -> emits brew install rtk" {
  _make_brew_stub
  run bash -c "export CLAUDE_RTK_PRINTER=echo; export CLAUDE_RTK_FORCE_CURL_FAIL=1; export CLAUDE_RTK_FORCE_CARGO_FAIL=1; export PATH='$TMP_DIR/bin:/usr/bin:/bin'; source '$LIB_DIR/install-rtk.sh'; install_rtk macos"
  [ "$status" -eq 0 ]
  [[ "$output" == *"brew"* ]]
  [[ "$output" == *"rtk"* ]]
}

@test "install_rtk: FORCE_CURL_FAIL + FORCE_CARGO_FAIL + brew stub + os=ubuntu -> does NOT use brew (rc 1)" {
  _make_brew_stub
  run bash -c "export CLAUDE_RTK_FORCE_CURL_FAIL=1; export CLAUDE_RTK_FORCE_CARGO_FAIL=1; export PATH='$TMP_DIR/bin:/usr/bin:/bin'; source '$LIB_DIR/install-rtk.sh'; install_rtk ubuntu"
  [ "$status" -ne 0 ]
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

# ---------- GAP-1: brew last-resort with INSTALL_PKG_CMD_PRINTER pre-set ----------

@test "install_rtk: brew last-resort with INSTALL_PKG_CMD_PRINTER pre-set -> caller value takes precedence and is restored" {
  # INSTALL_PKG_CMD_PRINTER is pre-set by the caller to a DISTINCT sentinel.
  # CLAUDE_RTK_PRINTER is set to a DIFFERENT sentinel.
  # After install_rtk returns, INSTALL_PKG_CMD_PRINTER must still equal the
  # caller's sentinel (not clobbered, not unset).
  _make_brew_stub
  local caller_printer_log="$TMP_DIR/caller_printer.log"
  local rtk_printer_log="$TMP_DIR/rtk_printer.log"

  # The caller's INSTALL_PKG_CMD_PRINTER sentinel logs to caller_printer_log.
  # We write a small script so it is an executable command name.
  mkdir -p "$TMP_DIR/bin"
  printf '#!/bin/sh\necho "$@" >> "%s"\n' "$caller_printer_log" > "$TMP_DIR/bin/caller_sentinel"
  chmod +x "$TMP_DIR/bin/caller_sentinel"

  printf '#!/bin/sh\necho "$@" >> "%s"\n' "$rtk_printer_log" > "$TMP_DIR/bin/rtk_sentinel"
  chmod +x "$TMP_DIR/bin/rtk_sentinel"

  run bash -c "
    export PATH='$TMP_DIR/bin:/usr/bin:/bin'
    export CLAUDE_RTK_FORCE_CURL_FAIL=1
    export CLAUDE_RTK_FORCE_CARGO_FAIL=1
    export CLAUDE_RTK_PRINTER='$TMP_DIR/bin/rtk_sentinel'
    export INSTALL_PKG_CMD_PRINTER='$TMP_DIR/bin/caller_sentinel'
    source '$LIB_DIR/install-rtk.sh'
    install_rtk macos
    # After install_rtk returns, INSTALL_PKG_CMD_PRINTER must equal the caller's value
    echo \"POST_INSTALL_PKG_CMD_PRINTER::\${INSTALL_PKG_CMD_PRINTER}\"
  "
  [ "$status" -eq 0 ]
  # The caller's printer captured the brew install command (not the rtk_sentinel)
  [ -f "$caller_printer_log" ]
  grep -q "rtk" "$caller_printer_log"
  # INSTALL_PKG_CMD_PRINTER was restored to the caller's sentinel after return
  [[ "$output" == *"POST_INSTALL_PKG_CMD_PRINTER::$TMP_DIR/bin/caller_sentinel"* ]]
}

# ---------- GAP-4: CLAUDE_RTK_HAS_RTK=0 -> proceeds to install ----------

@test "install_rtk: CLAUDE_RTK_HAS_RTK=0 -> proceeds to install (explicit-absent treated as not-present)" {
  # CLAUDE_RTK_HAS_RTK=0 exercises the '0) return 1' arm of _rtk_has_rtk.
  # install_rtk must NOT short-circuit (must attempt the curl installer).
  run bash -c "
    export CLAUDE_RTK_HAS_RTK=0
    export CLAUDE_RTK_PRINTER=echo
    source '$LIB_DIR/install-rtk.sh'
    install_rtk macos
  "
  [ "$status" -eq 0 ]
  # The curl installer command must be emitted (install was NOT skipped)
  [[ "$output" == *"curl"* ]]
}

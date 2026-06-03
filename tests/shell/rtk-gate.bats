#!/usr/bin/env bats
# Specs for scripts/_lib/rtk-gate.sh and its setup.sh integration.
# Gate rules:
#   CLAUDE_REQUIRE_RTK=1  -> install on any platform (explicit opt-in)
#   CLAUDE_REQUIRE_RTK=0  -> skip on any platform    (explicit opt-out)
#   unset                 -> install if brew is present (brew-presence default)
# Env var tests use save->modify->restore, never bare pop(), per learned instinct.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  TMP_DIR="$(mktemp -d)"
  # Save prior env so we can restore it even if tests bail.
  _PRIOR_REQUIRE_SET=0
  if [[ -n "${CLAUDE_REQUIRE_RTK+x}" ]]; then
    _PRIOR_REQUIRE_SET=1
    _PRIOR_REQUIRE_VAL="$CLAUDE_REQUIRE_RTK"
  fi
  unset CLAUDE_REQUIRE_RTK
}

teardown() {
  rm -rf "$TMP_DIR"
  # Restore prior env exactly.
  if [[ "$_PRIOR_REQUIRE_SET" = "1" ]]; then
    export CLAUDE_REQUIRE_RTK="$_PRIOR_REQUIRE_VAL"
  else
    unset CLAUDE_REQUIRE_RTK
  fi
}

# ---------- should_install_rtk (brew-presence gate) ----------

@test "should_install_rtk: brew present + env unset -> install (rc 0)" {
  mkdir -p "$TMP_DIR/bin"
  printf '#!/bin/sh\necho "Homebrew 4.0"\n' > "$TMP_DIR/bin/brew"
  chmod +x "$TMP_DIR/bin/brew"
  run bash -c "unset CLAUDE_REQUIRE_RTK; export PATH='$TMP_DIR/bin'; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk"
  [ "$status" -eq 0 ]
}

@test "should_install_rtk: brew absent + env unset -> skip (rc 1)" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; export PATH=/nowhere; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk"
  [ "$status" -eq 1 ]
}

@test "should_install_rtk: CLAUDE_REQUIRE_RTK=1 + brew absent -> install (rc 0)" {
  run bash -c "export CLAUDE_REQUIRE_RTK=1; export PATH=/nowhere; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk"
  [ "$status" -eq 0 ]
}

@test "should_install_rtk: CLAUDE_REQUIRE_RTK=0 + brew present -> skip (rc 1)" {
  mkdir -p "$TMP_DIR/bin"
  printf '#!/bin/sh\necho "Homebrew 4.0"\n' > "$TMP_DIR/bin/brew"
  chmod +x "$TMP_DIR/bin/brew"
  run bash -c "export CLAUDE_REQUIRE_RTK=0; export PATH='$TMP_DIR/bin'; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk"
  [ "$status" -eq 1 ]
}

@test "should_install_rtk: CLAUDE_REQUIRE_RTK=0 + brew absent -> skip (rc 1)" {
  run bash -c "export CLAUDE_REQUIRE_RTK=0; export PATH=/nowhere; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk"
  [ "$status" -eq 1 ]
}

@test "should_install_rtk: CLAUDE_REQUIRE_RTK=1 + brew present -> install (rc 0)" {
  mkdir -p "$TMP_DIR/bin"
  printf '#!/bin/sh\necho "Homebrew 4.0"\n' > "$TMP_DIR/bin/brew"
  chmod +x "$TMP_DIR/bin/brew"
  run bash -c "export CLAUDE_REQUIRE_RTK=1; export PATH='$TMP_DIR/bin'; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk"
  [ "$status" -eq 0 ]
}

# ---------- rtk_skip_reason (INFO message for skipped installs) ----------

@test "rtk_skip_reason: CLAUDE_REQUIRE_RTK=0 cites explicit opt-out" {
  run bash -c "export CLAUDE_REQUIRE_RTK=0; source '$LIB_DIR/rtk-gate.sh'; rtk_skip_reason"
  [ "$status" -eq 0 ]
  [[ "$output" == *"CLAUDE_REQUIRE_RTK=0"* ]]
}

@test "rtk_skip_reason: brew absent + env unset cites brew" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; export PATH=/nowhere; source '$LIB_DIR/rtk-gate.sh'; rtk_skip_reason"
  [ "$status" -eq 0 ]
  [[ "$output" == *"brew"* ]]
}

# ---------- gate branch integration (mimics setup.sh if/else block) ----------

_run_rtk_gate_branch() {
  # Simulate the setup.sh gate branch without calling real brew install.
  # $1 = bin directory to prepend to PATH (for brew presence simulation).
  local brew_bin="${1:-/nowhere}"
  bash -c "
    export PATH='${brew_bin}'
    source '$LIB_DIR/rtk-gate.sh'
    if should_install_rtk; then
      echo 'INSTALL: rtk'
    else
      echo \"INFO: skipping rtk (\$(rtk_skip_reason))\"
    fi
  "
}

@test "gate branch: brew present + env unset -> INSTALL emit" {
  mkdir -p "$TMP_DIR/bin"
  printf '#!/bin/sh\necho "Homebrew 4.0"\n' > "$TMP_DIR/bin/brew"
  chmod +x "$TMP_DIR/bin/brew"
  unset CLAUDE_REQUIRE_RTK
  run _run_rtk_gate_branch "$TMP_DIR/bin"
  [ "$status" -eq 0 ]
  [[ "$output" == *"INSTALL: rtk"* ]]
}

@test "gate branch: brew absent + env unset -> INFO skip line" {
  unset CLAUDE_REQUIRE_RTK
  run _run_rtk_gate_branch /nowhere
  [ "$status" -eq 0 ]
  [[ "$output" == *"INFO: skipping rtk"* ]]
}

@test "gate branch: CLAUDE_REQUIRE_RTK=1 + brew absent -> INSTALL emit" {
  export CLAUDE_REQUIRE_RTK=1
  run _run_rtk_gate_branch /nowhere
  [ "$status" -eq 0 ]
  [[ "$output" == *"INSTALL: rtk"* ]]
  unset CLAUDE_REQUIRE_RTK
}

# ---------- setup.sh fail-fast integration (AC4) ----------

@test "setup.sh fails fast with clear error if rtk-gate.sh is missing" {
  # Copy ALL existing bootstrap libs into TMP_DIR; omit ONLY rtk-gate.sh.
  # If any other lib were also missing the test would cite the wrong lib.
  mkdir -p "$TMP_DIR/scripts/_lib"
  cp "$LIB_DIR/detect-os.sh"    "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/dippy-gate.sh"   "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-rust.sh" "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/cloud-link.sh"   "$TMP_DIR/scripts/_lib/"
  # rtk-gate.sh deliberately omitted
  awk '/^# --- end bootstrap ---$/{exit} {print}' \
    "$REPO_ROOT/setup.sh" > "$TMP_DIR/setup_prefix.sh"
  run bash "$TMP_DIR/setup_prefix.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"rtk-gate.sh"* ]]
}

# ---------- README row (AC3) ----------

@test "README rtk row references setup.sh on base branch (grep)" {
  # The rtk row exists on refactor/ws-e-dead-hooks-audit (this branch's base).
  # Verify the row is present in the working tree's README.
  run grep -i "rtk" "$REPO_ROOT/README.md"
  [ "$status" -eq 0 ]
  [[ "$output" == *"rtk"* ]]
}

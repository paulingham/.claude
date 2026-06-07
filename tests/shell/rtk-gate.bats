#!/usr/bin/env bats
# Specs for scripts/_lib/rtk-gate.sh and its setup.sh integration.
# Gate rules (OS-arg based, rev 2):
#   CLAUDE_REQUIRE_RTK=1   -> install on any platform (explicit opt-in)
#   CLAUDE_REQUIRE_RTK=0   -> skip on any platform    (explicit opt-out)
#   unset                  -> install on macos|ubuntu|debian|fedora|arch|alpine
#                          -> skip on unknown
#   no arg                 -> rc 2 (caller error)
# Env var tests use save->modify->restore, never bare pop(), per learned instinct.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  TMP_DIR="$(mktemp -d)"
  _PRIOR_REQUIRE_SET=0
  if [[ -n "${CLAUDE_REQUIRE_RTK+x}" ]]; then
    _PRIOR_REQUIRE_SET=1
    _PRIOR_REQUIRE_VAL="$CLAUDE_REQUIRE_RTK"
  fi
  unset CLAUDE_REQUIRE_RTK
}

teardown() {
  rm -rf "$TMP_DIR"
  if [[ "$_PRIOR_REQUIRE_SET" = "1" ]]; then
    export CLAUDE_REQUIRE_RTK="$_PRIOR_REQUIRE_VAL"
  else
    unset CLAUDE_REQUIRE_RTK
  fi
}

# ---------- should_install_rtk OS-arg truth table ----------

@test "should_install_rtk: macos + env unset -> install (rc 0)" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk macos"
  [ "$status" -eq 0 ]
}

@test "should_install_rtk: ubuntu + env unset -> install (rc 0)" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk ubuntu"
  [ "$status" -eq 0 ]
}

@test "should_install_rtk: debian + env unset -> install (rc 0)" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk debian"
  [ "$status" -eq 0 ]
}

@test "should_install_rtk: fedora + env unset -> install (rc 0)" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk fedora"
  [ "$status" -eq 0 ]
}

@test "should_install_rtk: arch + env unset -> install (rc 0)" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk arch"
  [ "$status" -eq 0 ]
}

@test "should_install_rtk: alpine + env unset -> install (rc 0)" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk alpine"
  [ "$status" -eq 0 ]
}

@test "should_install_rtk: unknown + env unset -> skip (rc 1)" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk unknown"
  [ "$status" -eq 1 ]
}

@test "should_install_rtk: CLAUDE_REQUIRE_RTK=1 + unknown -> install (rc 0)" {
  run bash -c "export CLAUDE_REQUIRE_RTK=1; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk unknown"
  [ "$status" -eq 0 ]
}

@test "should_install_rtk: CLAUDE_REQUIRE_RTK=0 + macos -> skip (rc 1)" {
  run bash -c "export CLAUDE_REQUIRE_RTK=0; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk macos"
  [ "$status" -eq 1 ]
}

@test "should_install_rtk: no arg -> rc 2 (guard fires)" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; source '$LIB_DIR/rtk-gate.sh'; should_install_rtk"
  [ "$status" -eq 2 ]
}

# ---------- rtk_skip_reason ----------

@test "rtk_skip_reason: CLAUDE_REQUIRE_RTK=0 cites explicit opt-out" {
  run bash -c "export CLAUDE_REQUIRE_RTK=0; source '$LIB_DIR/rtk-gate.sh'; rtk_skip_reason unknown"
  [ "$status" -eq 0 ]
  [[ "$output" == *"CLAUDE_REQUIRE_RTK=0"* ]]
}

@test "rtk_skip_reason: unknown OS -> cites OS not brew" {
  run bash -c "unset CLAUDE_REQUIRE_RTK; source '$LIB_DIR/rtk-gate.sh'; rtk_skip_reason unknown"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OS=unknown"* ]]
  [[ "$output" != *"brew"* ]]
}

# ---------- setup.sh source-block fail-fast (new libs) ----------

@test "setup.sh fails fast with clear error if rtk-gate.sh is missing" {
  mkdir -p "$TMP_DIR/scripts/_lib"
  cp "$LIB_DIR/detect-os.sh"       "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/dippy-gate.sh"      "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-rust.sh"    "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-pkg.sh"     "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/cloud-link.sh"      "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-rtk.sh"     "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-node.sh"    "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-lsp-servers.sh" "$TMP_DIR/scripts/_lib/"
  # rtk-gate.sh deliberately omitted
  awk '/^# --- end bootstrap ---$/{exit} {print}' \
    "$REPO_ROOT/setup.sh" > "$TMP_DIR/setup_prefix.sh"
  run bash "$TMP_DIR/setup_prefix.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"rtk-gate.sh"* ]]
}

@test "setup.sh fails fast if install-rtk.sh missing" {
  mkdir -p "$TMP_DIR/scripts/_lib"
  cp "$LIB_DIR/detect-os.sh"       "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/dippy-gate.sh"      "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/rtk-gate.sh"        "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-rust.sh"    "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-pkg.sh"     "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/cloud-link.sh"      "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-node.sh"    "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-lsp-servers.sh" "$TMP_DIR/scripts/_lib/"
  # install-rtk.sh deliberately omitted
  awk '/^# --- end bootstrap ---$/{exit} {print}' \
    "$REPO_ROOT/setup.sh" > "$TMP_DIR/setup_prefix.sh"
  run bash "$TMP_DIR/setup_prefix.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"install-rtk.sh"* ]]
}

@test "setup.sh fails fast if install-node.sh missing" {
  mkdir -p "$TMP_DIR/scripts/_lib"
  cp "$LIB_DIR/detect-os.sh"          "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/dippy-gate.sh"         "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/rtk-gate.sh"           "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-rust.sh"       "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-pkg.sh"        "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/cloud-link.sh"         "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-rtk.sh"        "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-lsp-servers.sh" "$TMP_DIR/scripts/_lib/"
  # install-node.sh deliberately omitted
  awk '/^# --- end bootstrap ---$/{exit} {print}' \
    "$REPO_ROOT/setup.sh" > "$TMP_DIR/setup_prefix.sh"
  run bash "$TMP_DIR/setup_prefix.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"install-node.sh"* ]]
}

@test "setup.sh fails fast if install-lsp-servers.sh missing" {
  mkdir -p "$TMP_DIR/scripts/_lib"
  cp "$LIB_DIR/detect-os.sh"    "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/dippy-gate.sh"   "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/rtk-gate.sh"     "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-rust.sh" "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-pkg.sh"  "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/cloud-link.sh"   "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-rtk.sh"  "$TMP_DIR/scripts/_lib/"
  cp "$LIB_DIR/install-node.sh" "$TMP_DIR/scripts/_lib/"
  # install-lsp-servers.sh deliberately omitted
  awk '/^# --- end bootstrap ---$/{exit} {print}' \
    "$REPO_ROOT/setup.sh" > "$TMP_DIR/setup_prefix.sh"
  run bash "$TMP_DIR/setup_prefix.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"install-lsp-servers.sh"* ]]
}

# ---------- README row ----------

@test "README rtk row references universal installer, not brew-only" {
  run grep -i "rtk" "$REPO_ROOT/README.md"
  [ "$status" -eq 0 ]
  [[ "$output" != *"brew install rtk"* ]]
  [[ "$output" == *"CLAUDE_REQUIRE_RTK"* ]]
  [[ "$output" == *"setup.sh"* ]]
}

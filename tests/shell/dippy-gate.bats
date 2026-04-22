#!/usr/bin/env bats
# Specs for scripts/_lib/dippy-gate.sh and its setup.sh integration.
# Gate rules:
#   CLAUDE_REQUIRE_DIPPY=1  -> install on any OS
#   CLAUDE_REQUIRE_DIPPY=0  -> skip on any OS
#   unset                   -> macOS installs, Linux skips (OS default)
# Env var tests use save->modify->restore, never bare pop(), per learned instinct.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  TMP_DIR="$(mktemp -d)"
  # Save prior env so we can restore it even if tests bail.
  _PRIOR_REQUIRE_SET=0
  if [[ -n "${CLAUDE_REQUIRE_DIPPY+x}" ]]; then
    _PRIOR_REQUIRE_SET=1
    _PRIOR_REQUIRE_VAL="$CLAUDE_REQUIRE_DIPPY"
  fi
  unset CLAUDE_REQUIRE_DIPPY
}

teardown() {
  rm -rf "$TMP_DIR"
  # Restore prior env exactly.
  if [[ "$_PRIOR_REQUIRE_SET" = "1" ]]; then
    export CLAUDE_REQUIRE_DIPPY="$_PRIOR_REQUIRE_VAL"
  else
    unset CLAUDE_REQUIRE_DIPPY
  fi
}

# ---------- should_install_dippy (env-var-driven OS gate) ----------

@test "should_install_dippy: macos + env unset -> install (rc 0)" {
  run bash -c "unset CLAUDE_REQUIRE_DIPPY; source '$LIB_DIR/dippy-gate.sh'; should_install_dippy macos"
  [ "$status" -eq 0 ]
}

@test "should_install_dippy: ubuntu + env unset -> skip (rc 1)" {
  run bash -c "unset CLAUDE_REQUIRE_DIPPY; source '$LIB_DIR/dippy-gate.sh'; should_install_dippy ubuntu"
  [ "$status" -eq 1 ]
}

@test "should_install_dippy: debian + env unset -> skip (rc 1)" {
  run bash -c "unset CLAUDE_REQUIRE_DIPPY; source '$LIB_DIR/dippy-gate.sh'; should_install_dippy debian"
  [ "$status" -eq 1 ]
}

@test "should_install_dippy: ubuntu + CLAUDE_REQUIRE_DIPPY=1 -> install (rc 0)" {
  run bash -c "export CLAUDE_REQUIRE_DIPPY=1; source '$LIB_DIR/dippy-gate.sh'; should_install_dippy ubuntu"
  [ "$status" -eq 0 ]
}

@test "should_install_dippy: macos + CLAUDE_REQUIRE_DIPPY=0 -> skip (rc 1)" {
  run bash -c "export CLAUDE_REQUIRE_DIPPY=0; source '$LIB_DIR/dippy-gate.sh'; should_install_dippy macos"
  [ "$status" -eq 1 ]
}

@test "should_install_dippy: macos + CLAUDE_REQUIRE_DIPPY=1 -> install (rc 0, explicit opt-in)" {
  run bash -c "export CLAUDE_REQUIRE_DIPPY=1; source '$LIB_DIR/dippy-gate.sh'; should_install_dippy macos"
  [ "$status" -eq 0 ]
}

@test "should_install_dippy: ubuntu + CLAUDE_REQUIRE_DIPPY=0 -> skip (rc 1)" {
  run bash -c "export CLAUDE_REQUIRE_DIPPY=0; source '$LIB_DIR/dippy-gate.sh'; should_install_dippy ubuntu"
  [ "$status" -eq 1 ]
}

@test "should_install_dippy: rejects empty OS arg (rc != 0)" {
  run bash -c "source '$LIB_DIR/dippy-gate.sh'; should_install_dippy ''"
  [ "$status" -ne 0 ]
}

# ---------- dippy_skip_reason (INFO message for skipped installs) ----------

@test "dippy_skip_reason: ubuntu + env unset cites platform default" {
  run bash -c "unset CLAUDE_REQUIRE_DIPPY; source '$LIB_DIR/dippy-gate.sh'; dippy_skip_reason ubuntu"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ubuntu"* ]]
  [[ "$output" == *"CLAUDE_REQUIRE_DIPPY"* ]]
}

@test "dippy_skip_reason: any OS + CLAUDE_REQUIRE_DIPPY=0 cites explicit opt-out" {
  run bash -c "export CLAUDE_REQUIRE_DIPPY=0; source '$LIB_DIR/dippy-gate.sh'; dippy_skip_reason macos"
  [ "$status" -eq 0 ]
  [[ "$output" == *"CLAUDE_REQUIRE_DIPPY=0"* ]]
}

# ---------- setup.sh integration (end-to-end contract) ----------
# These tests exercise the dippy-install branch in setup.sh via the gate lib.
# They source dippy-gate.sh in a subshell that mimics setup.sh's gate block
# so we test the contract (env var -> OS decision -> skip reason) without
# driving all of setup.sh's I/O.

_run_gate_branch() {
  # Args: $1=os, stdout is the branch's emission (install-attempt or skip line).
  bash -c "
    source '$LIB_DIR/dippy-gate.sh'
    if should_install_dippy '$1'; then
      echo 'INSTALL: dippy + claude-devtools'
    else
      echo \"INFO: skipping dippy + claude-devtools (\$(dippy_skip_reason '$1'))\"
    fi
  "
}

@test "gate branch on linux with env unset -> INFO skip line cites platform (C3)" {
  unset CLAUDE_REQUIRE_DIPPY
  run _run_gate_branch ubuntu
  [ "$status" -eq 0 ]
  [[ "$output" == *"INFO: skipping dippy"* ]]
  [[ "$output" == *"ubuntu"* ]]
}

@test "gate branch on linux with CLAUDE_REQUIRE_DIPPY=1 -> install attempt (C3)" {
  export CLAUDE_REQUIRE_DIPPY=1
  run _run_gate_branch ubuntu
  [ "$status" -eq 0 ]
  [[ "$output" == *"INSTALL: dippy"* ]]
  unset CLAUDE_REQUIRE_DIPPY
}

@test "gate branch on macos with CLAUDE_REQUIRE_DIPPY=0 -> INFO skip with env var cited" {
  export CLAUDE_REQUIRE_DIPPY=0
  run _run_gate_branch macos
  [ "$status" -eq 0 ]
  [[ "$output" == *"INFO: skipping dippy"* ]]
  [[ "$output" == *"CLAUDE_REQUIRE_DIPPY=0"* ]]
  unset CLAUDE_REQUIRE_DIPPY
}

@test "gate branch on macos with env unset -> install attempt (default)" {
  unset CLAUDE_REQUIRE_DIPPY
  run _run_gate_branch macos
  [ "$status" -eq 0 ]
  [[ "$output" == *"INSTALL: dippy"* ]]
}

# ---------- setup.sh integrates the libs end-to-end ----------
# Integration is proven by the fail-fast tests below (which actually execute the
# setup.sh bootstrap prefix) and the compose tests (which exercise the same lib
# composition setup.sh performs). No grep-based coupling to implementation text.

@test "detect_os + should_install_dippy compose correctly on macos (setup.sh integration)" {
  # setup.sh feeds detect_os's output into should_install_dippy. Verify the
  # composition: a Darwin uname -> macos -> install branch.
  run bash -c "
    uname() { echo Darwin; }; export -f uname
    source '$LIB_DIR/detect-os.sh'
    source '$LIB_DIR/dippy-gate.sh'
    os=\$(detect_os)
    should_install_dippy \"\$os\" && echo 'INSTALL' || echo 'SKIP'
  "
  [ "$status" -eq 0 ]
  [[ "$output" == *"INSTALL"* ]]
}

@test "detect_os + should_install_dippy compose correctly on ubuntu (setup.sh integration)" {
  # Ubuntu -> detect_os returns 'ubuntu' -> default is skip.
  printf 'ID=ubuntu\n' > "$TMP_DIR/os-release"
  run bash -c "
    uname() { echo Linux; }; export -f uname
    OS_RELEASE_PATH='$TMP_DIR/os-release'
    source '$LIB_DIR/detect-os.sh'
    source '$LIB_DIR/dippy-gate.sh'
    os=\$(detect_os)
    should_install_dippy \"\$os\" && echo 'INSTALL' || echo 'SKIP'
  "
  [ "$status" -eq 0 ]
  [[ "$output" == *"SKIP"* ]]
}

@test "setup.sh fails fast with a clear error if dippy-gate.sh is missing" {
  # Hard-require: a missing gate lib is a packaging bug, not a silent fallback.
  # Extract the bootstrap source block (up to the end-marker) and run it in a
  # tempdir where detect-os.sh is present but dippy-gate.sh is not — asserts
  # non-zero exit + a diagnostic naming dippy-gate.sh specifically.
  mkdir -p "$TMP_DIR/scripts/_lib"
  cp "$LIB_DIR/detect-os.sh" "$TMP_DIR/scripts/_lib/"
  awk '/^# --- end bootstrap ---$/{exit} {print}' \
    "$REPO_ROOT/setup.sh" > "$TMP_DIR/setup_prefix.sh"
  run bash "$TMP_DIR/setup_prefix.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"dippy-gate.sh"* ]]
}

@test "setup.sh fails fast with a clear error if detect-os.sh is missing" {
  # Hard-require: OS detection is a packaging prerequisite. Missing lib = exit.
  mkdir -p "$TMP_DIR/scripts/_lib"
  cp "$LIB_DIR/dippy-gate.sh" "$TMP_DIR/scripts/_lib/"
  awk '/^# --- end bootstrap ---$/{exit} {print}' \
    "$REPO_ROOT/setup.sh" > "$TMP_DIR/setup_prefix.sh"
  run bash "$TMP_DIR/setup_prefix.sh"
  [ "$status" -ne 0 ]
  [[ "$output" == *"detect-os.sh"* ]]
}

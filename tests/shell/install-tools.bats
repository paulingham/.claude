#!/usr/bin/env bats
# Specs for scripts/install-tools.sh and its _lib/ companions.
# Hermetic: every test controls CLAUDE_VENV_PATH, PIP_CMD, OS_RELEASE_PATH,
# and INSTALL_PKG_CMD_PRINTER so no real side effects occur.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB_DIR="$REPO_ROOT/scripts/_lib"
  TMP_DIR="$(mktemp -d)"
}

teardown() {
  rm -rf "$TMP_DIR"
}

# ---------- detect_os (AC3.1) ----------

@test "detect_os returns macos when uname -s = Darwin" {
  run bash -c "uname() { echo Darwin; }; export -f uname; source '$LIB_DIR/detect-os.sh'; detect_os"
  [ "$status" -eq 0 ]
  [ "$output" = "macos" ]
}

@test "detect_os returns ubuntu when /etc/os-release has ID=ubuntu" {
  echo 'ID=ubuntu' > "$TMP_DIR/os-release"
  run bash -c "uname() { echo Linux; }; export -f uname; OS_RELEASE_PATH='$TMP_DIR/os-release' source '$LIB_DIR/detect-os.sh'; OS_RELEASE_PATH='$TMP_DIR/os-release' detect_os"
  [ "$status" -eq 0 ]
  [ "$output" = "ubuntu" ]
}

@test "detect_os strips quotes from ID value (ID=\"debian\")" {
  echo 'ID="debian"' > "$TMP_DIR/os-release"
  run bash -c "uname() { echo Linux; }; export -f uname; OS_RELEASE_PATH='$TMP_DIR/os-release' source '$LIB_DIR/detect-os.sh'; OS_RELEASE_PATH='$TMP_DIR/os-release' detect_os"
  [ "$status" -eq 0 ]
  [ "$output" = "debian" ]
}

@test "detect_os returns unknown for unrecognised ID" {
  echo 'ID=slackware' > "$TMP_DIR/os-release"
  run bash -c "uname() { echo Linux; }; export -f uname; OS_RELEASE_PATH='$TMP_DIR/os-release' source '$LIB_DIR/detect-os.sh'; OS_RELEASE_PATH='$TMP_DIR/os-release' detect_os"
  [ "$status" -eq 0 ]
  [ "$output" = "unknown" ]
}

@test "detect_os returns unknown when os-release file is missing" {
  run bash -c "uname() { echo Linux; }; export -f uname; OS_RELEASE_PATH='$TMP_DIR/nonexistent' source '$LIB_DIR/detect-os.sh'; OS_RELEASE_PATH='$TMP_DIR/nonexistent' detect_os"
  [ "$status" -eq 0 ]
  [ "$output" = "unknown" ]
}

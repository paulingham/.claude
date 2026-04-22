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

# ---------- install_pkg (AC3.2, AC3.3, AC3.4) ----------

@test "install_pkg prints brew install on macos via INSTALL_PKG_CMD_PRINTER" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; source '$LIB_DIR/install-pkg.sh'; install_pkg jq macos"
  [ "$status" -eq 0 ]
  [ "$output" = "brew install jq" ]
}

@test "install_pkg prints sudo apt-get on ubuntu" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; source '$LIB_DIR/install-pkg.sh'; install_pkg ripgrep ubuntu"
  [ "$status" -eq 0 ]
  [ "$output" = "sudo apt-get install -y ripgrep" ]
}

@test "install_pkg prints sudo apt-get on debian" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; source '$LIB_DIR/install-pkg.sh'; install_pkg jq debian"
  [ "$status" -eq 0 ]
  [ "$output" = "sudo apt-get install -y jq" ]
}

@test "install_pkg prints sudo dnf on fedora" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; source '$LIB_DIR/install-pkg.sh'; install_pkg jq fedora"
  [ "$status" -eq 0 ]
  [ "$output" = "sudo dnf install -y jq" ]
}

@test "install_pkg prints pacman on arch" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; source '$LIB_DIR/install-pkg.sh'; install_pkg jq arch"
  [ "$status" -eq 0 ]
  [ "$output" = "sudo pacman -S --noconfirm jq" ]
}

@test "install_pkg prints apk on alpine" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; source '$LIB_DIR/install-pkg.sh'; install_pkg jq alpine"
  [ "$status" -eq 0 ]
  [ "$output" = "sudo apk add --no-cache jq" ]
}

@test "install_pkg returns non-zero on unknown os" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; source '$LIB_DIR/install-pkg.sh'; install_pkg jq unknown"
  [ "$status" -ne 0 ]
}

# ---------- ensure_venv (AC3.5) ----------

@test "ensure_venv with PIP_CMD=echo prints pip command and does not invoke real pip" {
  local venv="$TMP_DIR/test-venv-$$"
  run bash -c "export CLAUDE_VENV_PATH='$venv' PIP_CMD='echo PIP:'; source '$LIB_DIR/ensure-venv.sh'; ensure_venv onnxruntime numpy tokenizers"
  [ "$status" -eq 0 ]
  [[ "$output" == *"PIP: onnxruntime numpy tokenizers"* ]]
}

@test "ensure_venv is idempotent: second call does not recreate venv" {
  local venv="$TMP_DIR/venv-idem"
  mkdir -p "$venv"  # simulate pre-existing venv
  local mtime_before; mtime_before=$(stat -f %m "$venv" 2>/dev/null || stat -c %Y "$venv")
  run bash -c "export CLAUDE_VENV_PATH='$venv' PIP_CMD='echo PIP:'; source '$LIB_DIR/ensure-venv.sh'; ensure_venv numpy"
  [ "$status" -eq 0 ]
  local mtime_after; mtime_after=$(stat -f %m "$venv" 2>/dev/null || stat -c %Y "$venv")
  [ "$mtime_before" = "$mtime_after" ]
}

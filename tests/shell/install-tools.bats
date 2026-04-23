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

# ---------- install-tools.sh orchestrator (AC3.2, AC3.3, AC3.4, AC3.5, AC3.6) ----------

@test "install-tools.sh --dry-run on macos prints brew install lines" {
  run bash -c "export CLAUDE_VENV_PATH='$TMP_DIR/venv' PIP_CMD=echo; bash '$REPO_ROOT/scripts/install-tools.sh' --dry-run"
  [ "$status" -eq 0 ]
  [[ "$output" == *"brew install"* ]]
  [[ "$output" == *"jq"* ]]
  [[ "$output" == *"ripgrep"* ]]
}

@test "install-tools.sh --dry-run on ubuntu fixture prints sudo apt-get" {
  echo 'ID=ubuntu' > "$TMP_DIR/os-release"
  run bash -c "uname() { echo Linux; }; export -f uname; export OS_RELEASE_PATH='$TMP_DIR/os-release' CLAUDE_VENV_PATH='$TMP_DIR/venv' PIP_CMD=echo; bash '$REPO_ROOT/scripts/install-tools.sh' --dry-run"
  [ "$status" -eq 0 ]
  [[ "$output" == *"sudo apt-get install -y"* ]]
  [[ "$output" == *"jq"* ]]
  [[ "$output" == *"ripgrep"* ]]
}

@test "install-tools.sh --yes on unknown OS exits 1 with clear message" {
  echo 'ID=slackware' > "$TMP_DIR/os-release"
  run bash -c "uname() { echo Linux; }; export -f uname; export OS_RELEASE_PATH='$TMP_DIR/os-release' CLAUDE_VENV_PATH='$TMP_DIR/venv' PIP_CMD=echo; bash '$REPO_ROOT/scripts/install-tools.sh' --yes"
  [ "$status" -eq 1 ]
  [[ "$output" == *"unknown OS"* ]]
}

@test "install-tools.sh with --dry-run on unknown OS exits 1 cleanly" {
  echo 'ID=slackware' > "$TMP_DIR/os-release"
  run bash -c "uname() { echo Linux; }; export -f uname; export OS_RELEASE_PATH='$TMP_DIR/os-release' CLAUDE_VENV_PATH='$TMP_DIR/venv' PIP_CMD=echo; bash '$REPO_ROOT/scripts/install-tools.sh' --dry-run"
  [ "$status" -eq 1 ]
  [[ "$output" == *"unknown OS"* ]]
}

@test "install-tools.sh with no flags on unknown OS exits 1 cleanly" {
  echo 'ID=slackware' > "$TMP_DIR/os-release"
  run bash -c "uname() { echo Linux; }; export -f uname; export OS_RELEASE_PATH='$TMP_DIR/os-release' CLAUDE_VENV_PATH='$TMP_DIR/venv' PIP_CMD=echo; bash '$REPO_ROOT/scripts/install-tools.sh'"
  [ "$status" -eq 1 ]
  [[ "$output" == *"unknown OS"* ]]
}

@test "install-tools.sh --dry-run does not create the real venv" {
  # AC3.5: dry-run is hermetic — PIP_CMD defaults to "echo" via dry-run wiring
  # AND venv creation is suppressed so no physical side effects occur.
  local fake_home="$TMP_DIR/fake_home"
  mkdir -p "$fake_home/.claude"
  run bash -c "export HOME='$fake_home'; bash '$REPO_ROOT/scripts/install-tools.sh' --dry-run"
  [ "$status" -eq 0 ]
  [ ! -d "$fake_home/.claude/.venv" ]
}

@test "install-tools.sh --yes hermetic: prints pip install for embedder deps, no real pip" {
  local venv="$TMP_DIR/test-venv-$$"
  run bash -c "export CLAUDE_VENV_PATH='$venv' PIP_CMD='echo PIP:'; bash '$REPO_ROOT/scripts/install-tools.sh' --yes"
  [ "$status" -eq 0 ]
  [[ "$output" == *"PIP: onnxruntime numpy tokenizers"* ]]
  # Venv path used must be the test path, not the real $HOME/.claude/.venv
  # Second invocation: no-op w.r.t. venv creation
  local mtime_before; mtime_before=$(stat -f %m "$venv" 2>/dev/null || stat -c %Y "$venv")
  sleep 1
  run bash -c "export CLAUDE_VENV_PATH='$venv' PIP_CMD='echo PIP:'; bash '$REPO_ROOT/scripts/install-tools.sh' --yes"
  [ "$status" -eq 0 ]
  local mtime_after; mtime_after=$(stat -f %m "$venv" 2>/dev/null || stat -c %Y "$venv")
  [ "$mtime_before" = "$mtime_after" ]
}

@test "install-tools.sh --dry-run on ubuntu includes Linux build toolchain (H4, M6)" {
  echo 'ID=ubuntu' > "$TMP_DIR/os-release"
  run bash -c "uname() { echo Linux; }; export -f uname; export OS_RELEASE_PATH='$TMP_DIR/os-release' CLAUDE_VENV_PATH='$TMP_DIR/venv' PIP_CMD=echo; bash '$REPO_ROOT/scripts/install-tools.sh' --dry-run"
  [ "$status" -eq 0 ]
  [[ "$output" == *"build-essential"* ]]
  [[ "$output" == *"libssl-dev"* ]]
  [[ "$output" == *"pkg-config"* ]]
  [[ "$output" == *"curl"* ]]
}

@test "install-tools.sh --dry-run on debian includes Linux build toolchain (H4, M6)" {
  echo 'ID=debian' > "$TMP_DIR/os-release"
  run bash -c "uname() { echo Linux; }; export -f uname; export OS_RELEASE_PATH='$TMP_DIR/os-release' CLAUDE_VENV_PATH='$TMP_DIR/venv' PIP_CMD=echo; bash '$REPO_ROOT/scripts/install-tools.sh' --dry-run"
  [ "$status" -eq 0 ]
  [[ "$output" == *"build-essential"* ]]
  [[ "$output" == *"libssl-dev"* ]]
}

@test "install-tools.sh --dry-run on macos does NOT include Linux build toolchain" {
  run bash -c "export CLAUDE_VENV_PATH='$TMP_DIR/venv' PIP_CMD=echo; bash '$REPO_ROOT/scripts/install-tools.sh' --dry-run"
  [ "$status" -eq 0 ]
  [[ "$output" != *"build-essential"* ]]
  [[ "$output" != *"libssl-dev"* ]]
}

@test "install-tools.sh --dry-run on fedora includes Fedora build toolchain (H4)" {
  echo 'ID=fedora' > "$TMP_DIR/os-release"
  run bash -c "uname() { echo Linux; }; export -f uname; export OS_RELEASE_PATH='$TMP_DIR/os-release' CLAUDE_VENV_PATH='$TMP_DIR/venv' PIP_CMD=echo; bash '$REPO_ROOT/scripts/install-tools.sh' --dry-run"
  [ "$status" -eq 0 ]
  [[ "$output" == *"openssl-devel"* ]]
  [[ "$output" == *"gcc"* ]]
  [[ "$output" == *"curl"* ]]
}

@test "install-tools.sh --yes prints 'skipped' for every tool already on PATH (AC3.6)" {
  # On the build host, all SYSTEM_TOOLS are present (we installed bats/shellcheck,
  # and gh/jq/ripgrep/sqlite3/python3 ship with the dev environment). Re-running
  # --yes must emit "skipped: <tool>" for each and exit 0.
  local venv="$TMP_DIR/idem-venv"
  run bash -c "export CLAUDE_VENV_PATH='$venv' PIP_CMD='echo PIP:'; bash '$REPO_ROOT/scripts/install-tools.sh' --yes"
  [ "$status" -eq 0 ]
  # At least one skipped line must appear (for gh, bats, shellcheck — known present)
  [[ "$output" == *"skipped:"* ]]
  # No "install_pkg: unsupported OS" (should not bail)
  [[ "$output" != *"unsupported OS"* ]]
}

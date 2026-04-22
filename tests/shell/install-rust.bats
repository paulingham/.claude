#!/usr/bin/env bats
# M1: rust toolchain install should prefer the distro package manager on
# Linux (apt/dnf/etc via install-pkg.sh) and fall back to the rustup
# installer only when the distro path fails or cargo remains absent.
# macOS keeps the rustup installer (brew ships no 'cargo' formula).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  LIB="$REPO_ROOT/scripts/_lib/install-rust.sh"
}

@test "M1.1 install_rust_toolchain ubuntu uses apt-get via install_pkg" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; export CLAUDE_RUST_HAS_CARGO=0; source '$LIB'; install_rust_toolchain ubuntu"
  [ "$status" -eq 0 ]
  [[ "$output" == *"sudo apt-get install -y cargo rustc"* ]]
}

@test "M1.2 install_rust_toolchain debian uses apt-get via install_pkg" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; export CLAUDE_RUST_HAS_CARGO=0; source '$LIB'; install_rust_toolchain debian"
  [ "$status" -eq 0 ]
  [[ "$output" == *"sudo apt-get install -y cargo rustc"* ]]
}

@test "M1.3 install_rust_toolchain fedora uses dnf via install_pkg" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; export CLAUDE_RUST_HAS_CARGO=0; source '$LIB'; install_rust_toolchain fedora"
  [ "$status" -eq 0 ]
  [[ "$output" == *"sudo dnf install -y cargo rust"* ]]
}

@test "M1.4 install_rust_toolchain macos uses rustup installer (printed, not run)" {
  run bash -c "export CLAUDE_RUST_PRINTER=echo; export CLAUDE_RUST_HAS_CARGO=0; source '$LIB'; install_rust_toolchain macos"
  [ "$status" -eq 0 ]
  [[ "$output" == *"rustup"* ]]
  [[ "$output" != *"sudo apt-get"* ]]
  [[ "$output" != *"sudo dnf"* ]]
}

@test "M1.5 install_rust_toolchain is a no-op when cargo already present" {
  run bash -c "export INSTALL_PKG_CMD_PRINTER=echo; export CLAUDE_RUST_HAS_CARGO=1; source '$LIB'; install_rust_toolchain ubuntu"
  [ "$status" -eq 0 ]
  [[ "$output" != *"apt-get"* ]]
  [[ "$output" != *"rustup"* ]]
}

@test "M1.6 install_rust_toolchain falls back to rustup when distro install fails" {
  run bash -c "export CLAUDE_RUST_FORCE_DISTRO_FAIL=1; export CLAUDE_RUST_PRINTER=echo; export CLAUDE_RUST_HAS_CARGO=0; source '$LIB'; install_rust_toolchain ubuntu"
  [ "$status" -eq 0 ]
  [[ "$output" == *"rustup"* ]]
}

@test "M1.7 install_rust_toolchain returns non-zero on unknown OS" {
  run bash -c "export CLAUDE_RUST_HAS_CARGO=0; source '$LIB'; install_rust_toolchain slackware"
  [ "$status" -ne 0 ]
}

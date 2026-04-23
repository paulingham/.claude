#!/usr/bin/env bash
# install_rust_toolchain <os> — installs cargo+rustc via the OS package
# manager on Linux, falling back to the upstream rustup installer if the
# distro path fails or the 'cargo' command is still absent afterwards.
# macOS always uses the rustup installer (brew ships no 'cargo' formula).
#
# Hermetic controls for tests:
#   CLAUDE_RUST_HAS_CARGO=1  — short-circuit (treat cargo as already present)
#   CLAUDE_RUST_PRINTER=echo — capture rustup command instead of curl | sh
#   INSTALL_PKG_CMD_PRINTER  — forwarded to install_pkg (see install-pkg.sh)

_install_rust_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_install_rust_dir/install-pkg.sh"

_rust_has_cargo() {
  case "${CLAUDE_RUST_HAS_CARGO:-auto}" in 1) return 0 ;; 0) return 1 ;; esac
  command -v cargo >/dev/null 2>&1
}

_rust_distro_pkgs() {
  case "$1" in
    ubuntu|debian|arch|alpine) echo "cargo rustc" ;;
    fedora) echo "cargo rust" ;;
    *) return 1 ;;
  esac
}

_rust_try_distro() {
  [[ "${CLAUDE_RUST_FORCE_DISTRO_FAIL:-}" == "1" ]] && return 1
  local pkgs; pkgs=$(_rust_distro_pkgs "$1") || return 1
  install_pkg "$pkgs" "$1"
}

_rust_run_rustup() {
  local cmd="curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"
  local printer="${CLAUDE_RUST_PRINTER:-}"
  [[ -n "$printer" ]] && { "$printer" "$cmd"; return 0; }
  eval "$cmd"
}

install_rust_toolchain() {
  local os="$1"
  _rust_has_cargo && return 0
  case "$os" in macos|unknown) : ;; ubuntu|debian|fedora|arch|alpine) _rust_try_distro "$os" && return 0 ;; *) return 1 ;; esac
  _rust_run_rustup
}

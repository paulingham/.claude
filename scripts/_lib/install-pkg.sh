#!/usr/bin/env bash
# install_pkg <pkg> <os> — dispatches to the native package manager.
# Tests set INSTALL_PKG_CMD_PRINTER=echo to capture the command without
# executing it. When unset, the resolved command runs for real.

_pkg_cmd_for_os() {
  case "$2" in
    macos) echo "brew install $1" ;;
    ubuntu|debian) echo "sudo apt-get install -y $1" ;;
    fedora) echo "sudo dnf install -y $1" ;;
    arch) echo "sudo pacman -S --noconfirm $1" ;;
    alpine) echo "sudo apk add --no-cache $1" ;;
    *) return 1 ;;
  esac
}

install_pkg() {
  local cmd
  cmd=$(_pkg_cmd_for_os "$1" "$2") || { echo "install_pkg: unsupported OS '$2'" >&2; return 1; }
  [[ -n "${INSTALL_PKG_CMD_PRINTER:-}" ]] && { "$INSTALL_PKG_CMD_PRINTER" "$cmd"; return 0; }
  eval "$cmd"
}

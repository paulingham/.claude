#!/usr/bin/env bash
# install_pkg <pkg> <os> — dispatches to the native package manager.
# Tests set INSTALL_PKG_CMD_PRINTER=echo to capture the command without
# executing it. When unset, the resolved command runs for real.

_pm_prefix_for_os() {
  case "$1" in
    macos) echo "brew install" ;;
    ubuntu|debian) echo "sudo apt-get install -y" ;;
    fedora) echo "sudo dnf install -y" ;;
    arch) echo "sudo pacman -S --noconfirm" ;;
    alpine) echo "sudo apk add --no-cache" ;;
    *) return 1 ;;
  esac
}

_pkg_cmd_for_os() {
  local prefix; prefix=$(_pm_prefix_for_os "$2") || return 1
  echo "$prefix $1"
}

install_pkg() {
  local cmd
  cmd=$(_pkg_cmd_for_os "$1" "$2") || { echo "install_pkg: unsupported OS '$2'" >&2; return 1; }
  [[ -n "${INSTALL_PKG_CMD_PRINTER:-}" ]] && { "$INSTALL_PKG_CMD_PRINTER" "$cmd"; return 0; }
  eval "$cmd"
}

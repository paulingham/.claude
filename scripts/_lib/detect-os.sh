#!/usr/bin/env bash
# detect_os — prints one of: macos|ubuntu|debian|fedora|arch|alpine|unknown
# Tests override OS_RELEASE_PATH to point at a fixture; default /etc/os-release.
# Portable across bash 3.2 (macOS default) and bash 5+ (Linux).

_os_release_id() {
  local f="${OS_RELEASE_PATH:-/etc/os-release}"
  [[ -r "$f" ]] || { echo unknown; return 0; }
  awk -F= '$1=="ID"{gsub(/"/,"",$2); print $2; exit}' "$f"
}

_normalise_os_id() {
  case "$1" in ubuntu|debian|fedora|arch|alpine) echo "$1" ;; *) echo unknown ;; esac
}

detect_os() {
  [[ "$(uname -s)" == "Darwin" ]] && { echo macos; return 0; }
  _normalise_os_id "$(_os_release_id)"
}

#!/usr/bin/env bash
# install_rtk — installs the rtk CLI token-optimization proxy.
# Install method order: curl universal installer -> cargo fallback -> brew last-resort.
# Idempotent: no-op if rtk already on PATH.
#
# Hermetic controls for tests:
#   CLAUDE_RTK_HAS_RTK=1          — short-circuit (treat rtk as already present)
#   CLAUDE_RTK_PRINTER=echo       — capture installer command instead of running it
#   CLAUDE_RTK_FORCE_CURL_FAIL=1  — skip curl installer (force cargo path)
#   CLAUDE_RTK_FORCE_CARGO_FAIL=1 — skip cargo install (force brew path)
#   INSTALL_PKG_CMD_PRINTER       — forwarded to install_pkg (see install-pkg.sh)

_install_rtk_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_install_rtk_dir/install-pkg.sh"

_rtk_has_rtk() {
  case "${CLAUDE_RTK_HAS_RTK:-auto}" in 1) return 0 ;; 0) return 1 ;; esac
  command -v rtk >/dev/null 2>&1
}

_rtk_run_installer() {
  [[ "${CLAUDE_RTK_FORCE_CURL_FAIL:-}" == "1" ]] && return 1
  local cmd="curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh"
  local printer="${CLAUDE_RTK_PRINTER:-}"
  if [[ -n "$printer" ]]; then
    "$printer" "$cmd"
    return 0
  fi
  eval "$cmd"
  # Re-check that the binary is actually present after install (pre-mortem mitigation)
  command -v rtk >/dev/null 2>&1
}

_rtk_run_cargo() {
  [[ "${CLAUDE_RTK_FORCE_CARGO_FAIL:-}" == "1" ]] && return 1
  command -v cargo >/dev/null 2>&1 || return 1
  local cmd="cargo install --git https://github.com/rtk-ai/rtk"
  local printer="${CLAUDE_RTK_PRINTER:-}"
  if [[ -n "$printer" ]]; then
    "$printer" "$cmd"
    return 0
  fi
  eval "$cmd"
  # Re-check binary presence after install
  command -v rtk >/dev/null 2>&1
}

_rtk_run_brew() {
  command -v brew >/dev/null 2>&1 || return 1
  local _saved="${INSTALL_PKG_CMD_PRINTER:-}"
  export INSTALL_PKG_CMD_PRINTER="${INSTALL_PKG_CMD_PRINTER:-${CLAUDE_RTK_PRINTER:-}}"
  install_pkg rtk macos
  local _rc=$?
  if [[ -z "$_saved" ]]; then
    unset INSTALL_PKG_CMD_PRINTER
  else
    export INSTALL_PKG_CMD_PRINTER="$_saved"
  fi
  return $_rc
}

install_rtk() {
  _rtk_has_rtk && return 0
  _rtk_run_installer && return 0
  _rtk_run_cargo && return 0
  _rtk_run_brew && return 0
  return 1
}

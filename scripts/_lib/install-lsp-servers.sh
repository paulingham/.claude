#!/usr/bin/env bash
# ensure_lsp_servers — installs typescript-language-server and pyright via npm -g.
# Idempotent per binary: skips each server if already on PATH.
# Continue-on-failure: each install is independent; rc tracks failures.
# Requires npm on PATH. Never uses Homebrew.
#
# Hermetic controls for tests:
#   CLAUDE_LSP_HAS_TSSERVER=1  — treat typescript-language-server as present
#   CLAUDE_LSP_HAS_PYRIGHT=1   — treat pyright as present
#   CLAUDE_LSP_PRINTER=echo    — capture npm command instead of running it

_lsp_has_tsserver() {
  case "${CLAUDE_LSP_HAS_TSSERVER:-auto}" in 1) return 0 ;; 0) return 1 ;; esac
  command -v typescript-language-server >/dev/null 2>&1
}

_lsp_has_pyright() {
  case "${CLAUDE_LSP_HAS_PYRIGHT:-auto}" in 1) return 0 ;; 0) return 1 ;; esac
  command -v pyright >/dev/null 2>&1
}

_lsp_install_pkg() {
  local pkg="$1"
  local cmd="npm install -g $pkg"
  local printer="${CLAUDE_LSP_PRINTER:-}"
  if [[ -n "$printer" ]]; then
    "$printer" "$cmd"
    return 0
  fi
  eval "$cmd"
}

ensure_lsp_servers() {
  command -v npm >/dev/null 2>&1 || return 1
  local _rc=0
  if ! _lsp_has_tsserver; then
    _lsp_install_pkg typescript-language-server || _rc=1
  fi
  if ! _lsp_has_pyright; then
    _lsp_install_pkg pyright || _rc=1
  fi
  return $_rc
}

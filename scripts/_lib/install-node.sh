#!/usr/bin/env bash
# install_node_via_manager <os> — installs Node LTS via an existing version manager
# (nvm → fnm → mise → asdf) or installs nvm if none is found.
# Idempotent: no-op if node already on PATH. NEVER uses Homebrew.
# <os> accepted for call-site symmetry; manager chain is OS-agnostic.
#
# nvm is a shell function defined in $NVM_DIR/nvm.sh — non-interactive bash
# shells do NOT source ~/.bashrc, so the lib sources nvm.sh explicitly.
#
# Hermetic controls for tests:
#   CLAUDE_NODE_HAS_NODE=1           — short-circuit (treat node as present)
#   CLAUDE_NODE_PRINTER=echo         — capture install command instead of running
#   CLAUDE_NODE_FORCE_NVM_PRESENT=1  — simulate nvm detected
#   CLAUDE_NODE_FORCE_FNM_PRESENT=1  — simulate fnm detected
#   CLAUDE_NODE_FORCE_INSTALL_FAIL=1 — force all install paths to fail
#   NVM_DIR=<path>                   — redirect nvm home (default: $HOME/.nvm)

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

_node_has_node() {
  case "${CLAUDE_NODE_HAS_NODE:-auto}" in 1) return 0 ;; 0) return 1 ;; esac
  command -v node >/dev/null 2>&1
}

_node_has_nvm() {
  [[ "${CLAUDE_NODE_FORCE_NVM_PRESENT:-}" == "1" ]] && return 0
  [[ -s "$NVM_DIR/nvm.sh" ]]
}

_node_has_fnm() {
  [[ "${CLAUDE_NODE_FORCE_FNM_PRESENT:-}" == "1" ]] && return 0
  command -v fnm >/dev/null 2>&1
}

_node_has_mise() {
  command -v mise >/dev/null 2>&1
}

_node_has_asdf() {
  command -v asdf >/dev/null 2>&1
}

_node_install_via_nvm() {
  local printer="${CLAUDE_NODE_PRINTER:-}"
  if [[ -n "$printer" ]]; then
    "$printer" "nvm install --lts"
    "$printer" "nvm use --lts"
    return 0
  fi
  # shellcheck disable=SC1090
  source "$NVM_DIR/nvm.sh" || return 1
  nvm install --lts || return 1
  nvm use --lts || return 1
  if [[ -z "${NVM_BIN:-}" ]]; then
    NVM_BIN="$(nvm which current | xargs dirname 2>/dev/null)"
  fi
  [[ -n "$NVM_BIN" ]] && export PATH="$NVM_BIN:$PATH"
  return 0
}

_node_install_via_fnm() {
  local printer="${CLAUDE_NODE_PRINTER:-}"
  if [[ -n "$printer" ]]; then
    "$printer" "fnm install --lts-latest"
    return 0
  fi
  fnm install --lts-latest || return 1
  eval "$(fnm env)" 2>/dev/null || true
  return 0
}

_node_install_via_mise() {
  local printer="${CLAUDE_NODE_PRINTER:-}"
  if [[ -n "$printer" ]]; then
    "$printer" "mise install node@lts"
    return 0
  fi
  mise install node@lts || return 1
  eval "$(mise activate bash)" 2>/dev/null || true
  return 0
}

_node_install_via_asdf() {
  local printer="${CLAUDE_NODE_PRINTER:-}"
  if [[ -n "$printer" ]]; then
    "$printer" "asdf install nodejs lts"
    return 0
  fi
  asdf install nodejs lts || return 1
  asdf reshim nodejs 2>/dev/null || true
  return 0
}

_node_install_nvm_then_node() {
  local cmd="curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/HEAD/install.sh | bash"
  local printer="${CLAUDE_NODE_PRINTER:-}"
  if [[ -n "$printer" ]]; then
    "$printer" "$cmd"
    return 0
  fi
  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/HEAD/install.sh | bash || return 1
  # Source the freshly-installed nvm.sh
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  # shellcheck disable=SC1090
  [[ -s "$NVM_DIR/nvm.sh" ]] && source "$NVM_DIR/nvm.sh" || return 1
  nvm install --lts || return 1
  nvm use --lts || return 1
  if [[ -z "${NVM_BIN:-}" ]]; then
    NVM_BIN="$(nvm which current | xargs dirname 2>/dev/null)"
  fi
  [[ -n "$NVM_BIN" ]] && export PATH="$NVM_BIN:$PATH"
  return 0
}

install_node_via_manager() {
  local os="${1:-}"
  _node_has_node && return 0
  [[ "${CLAUDE_NODE_FORCE_INSTALL_FAIL:-}" == "1" ]] && return 1
  if _node_has_nvm; then
    _node_install_via_nvm && return 0
  elif _node_has_fnm; then
    _node_install_via_fnm && return 0
  elif _node_has_mise; then
    _node_install_via_mise && return 0
  elif _node_has_asdf; then
    _node_install_via_asdf && return 0
  else
    _node_install_nvm_then_node && return 0
  fi
  return 1
}

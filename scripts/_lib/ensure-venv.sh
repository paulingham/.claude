#!/usr/bin/env bash
# ensure_venv <pkg...> — creates the venv at $CLAUDE_VENV_PATH (idempotent)
# and invokes $PIP_CMD with the supplied packages.
# Tests set PIP_CMD=echo to capture pip invocations without executing them.

_venv_path() { echo "${CLAUDE_VENV_PATH:-$HOME/.claude/.venv}"; }

_ensure_venv_dir() {
  local venv; venv=$(_venv_path)
  [[ -d "$venv" ]] && return 0
  [[ -n "${CLAUDE_VENV_DRY_RUN:-}" ]] && { echo "would create venv at $venv"; return 0; }
  python3 -m venv "$venv"
}

ensure_venv() {
  _ensure_venv_dir || return 1
  local pip="${PIP_CMD:-pip install}"
  # shellcheck disable=SC2086
  $pip "$@"
}

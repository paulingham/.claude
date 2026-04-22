#!/usr/bin/env bash
# install-tools.sh — OS-aware tool installer for the claude harness.
# Flags: --dry-run (print commands, no side effects), --yes (execute),
# neither (print commands + exit 1).
# Hermetic env: CLAUDE_VENV_PATH, PIP_CMD, OS_RELEASE_PATH, INSTALL_PKG_CMD_PRINTER.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib/detect-os.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib/install-pkg.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib/ensure-venv.sh"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_lib/build-tools.sh"

SYSTEM_TOOLS=(gh jq ripgrep sqlite3 python3 bats shellcheck)
PY_DEPS=(onnxruntime numpy tokenizers)

_pkg_name() { [[ "$1" == "bats" && "$2" == "macos" ]] && echo "bats-core" || echo "$1"; }

_process_tool() {
  local tool="$1" os="$2" mode="$3"
  command -v "$tool" >/dev/null 2>&1 && [[ "$mode" != "dry-run" ]] && { echo "skipped: $tool"; return 0; }
  install_pkg "$(_pkg_name "$tool" "$os")" "$os"
}

_mode_from_args() {
  case "${1:-}" in --dry-run) echo dry-run ;; --yes) echo yes ;; *) echo none ;; esac
}

_guard_unknown_os() {
  [[ "$1" != "unknown" ]] || { echo "unknown OS; cannot proceed" >&2; exit 1; }
}

_apply_mode_env() {
  [[ "$1" == "dry-run" || "$1" == "none" ]] || return 0
  export INSTALL_PKG_CMD_PRINTER=echo PIP_CMD="${PIP_CMD:-echo pip install}" CLAUDE_VENV_DRY_RUN=1
}

_install_build_tools() {
  local os="$1" mode="$2" pkg
  for pkg in $(build_tools_for_os "$os"); do _process_tool "$pkg" "$os" "$mode"; done
}

main() {
  local os mode; os=$(detect_os); mode=$(_mode_from_args "${1:-}")
  _guard_unknown_os "$os"; _apply_mode_env "$mode"
  for t in "${SYSTEM_TOOLS[@]}"; do _process_tool "$t" "$os" "$mode"; done
  _install_build_tools "$os" "$mode"
  ensure_venv "${PY_DEPS[@]}"
  [[ "$mode" != "none" ]] || { echo "re-run with --yes to execute" >&2; exit 1; }
}

main "$@"

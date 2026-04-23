#!/usr/bin/env bash
# dippy-gate.sh — decides whether setup.sh should install dippy + claude-devtools.
# These are Homebrew-only tools; on Linux they fail unless the user has a
# custom install path. The env var CLAUDE_REQUIRE_DIPPY overrides the OS default.
#
# Rules:
#   CLAUDE_REQUIRE_DIPPY=1  -> install on any OS (explicit opt-in)
#   CLAUDE_REQUIRE_DIPPY=0  -> skip on any OS    (explicit opt-out)
#   unset                   -> macOS installs, others skip (OS default)

_dippy_os_default_installs() {
  [[ "$1" == "macos" ]]
}

should_install_dippy() {
  local os="${1:-}"; [[ -n "$os" ]] || return 2
  case "${CLAUDE_REQUIRE_DIPPY:-}" in
    1) return 0 ;;
    0) return 1 ;;
    *) _dippy_os_default_installs "$os" && return 0 || return 1 ;;
  esac
}

dippy_skip_reason() {
  local os="${1:-}"
  case "${CLAUDE_REQUIRE_DIPPY:-}" in
    0) echo "CLAUDE_REQUIRE_DIPPY=0 (explicit opt-out)" ;;
    *) echo "platform=${os}; set CLAUDE_REQUIRE_DIPPY=1 to force install" ;;
  esac
}

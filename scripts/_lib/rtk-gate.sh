#!/usr/bin/env bash
# rtk-gate.sh — decides whether setup.sh should install rtk.
# rtk is a plain homebrew-core formula (no tap, no cask), bottled for macOS
# and Linux-with-linuxbrew. The gate is brew-presence based (not OS-based)
# because settings.json registers rtk unconditionally on all platforms.
#
# Rules:
#   CLAUDE_REQUIRE_RTK=1  -> install on any platform (explicit opt-in)
#   CLAUDE_REQUIRE_RTK=0  -> skip on any platform    (explicit opt-out)
#   unset                 -> install if brew is in PATH (brew-presence default)

_rtk_brew_exists() {
  command -v brew > /dev/null 2>&1
}

should_install_rtk() {
  case "${CLAUDE_REQUIRE_RTK:-}" in
    1) return 0 ;;
    0) return 1 ;;
    *) _rtk_brew_exists && return 0 || return 1 ;;
  esac
}

rtk_skip_reason() {
  case "${CLAUDE_REQUIRE_RTK:-}" in
    0) echo "CLAUDE_REQUIRE_RTK=0 (explicit opt-out)" ;;
    *) echo "brew not found; set CLAUDE_REQUIRE_RTK=1 to force install" ;;
  esac
}

#!/usr/bin/env bash
# rtk-gate.sh — decides whether setup.sh should install rtk.
# rtk is a CLI token-optimization proxy (github.com/rtk-ai/rtk) that compresses
# dev-tool output before it reaches the LLM. Integrates with Claude Code via
# a PreToolUse hook. The gate is OS-based (not brew-presence based) — Linux
# machines have no brew yet still benefit from rtk.
#
# Rules:
#   CLAUDE_REQUIRE_RTK=1  -> install on any platform (explicit opt-in)
#   CLAUDE_REQUIRE_RTK=0  -> skip on any platform    (explicit opt-out)
#   unset                 -> install on macos|ubuntu|debian|fedora|arch|alpine
#                         -> skip on unknown

should_install_rtk() {
  local os="${1:-}"; [[ -n "$os" ]] || return 2
  case "${CLAUDE_REQUIRE_RTK:-}" in
    1) return 0 ;;
    0) return 1 ;;
    *) case "$os" in
         macos|ubuntu|debian|fedora|arch|alpine) return 0 ;;
         *) return 1 ;;
       esac ;;
  esac
}

rtk_skip_reason() {
  local os="${1:-}"
  case "${CLAUDE_REQUIRE_RTK:-}" in
    0) echo "CLAUDE_REQUIRE_RTK=0 (explicit opt-out)" ;;
    *) echo "OS=${os}; set CLAUDE_REQUIRE_RTK=1 to force install" ;;
  esac
}

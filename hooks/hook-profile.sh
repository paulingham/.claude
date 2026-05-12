#!/usr/bin/env bash
# Hook profile gating — source this at the top of hooks to enable runtime profile control.
# Usage: check_hook_profile "standard" || exit 0
#
# Profiles (set via CLAUDE_HOOK_PROFILE env var, default: standard):
#   minimal  — blocking/security hooks only (quality-gate, orchestrator-discipline)
#   standard — all hooks (default)
#   strict   — all hooks (same as standard; reserved for future stricter checks)
#
# enforces: protocols/agent-protocol.md:Hook Profile
# protects: pipeline
check_hook_profile() {
  local required_level="$1"
  local profile="${CLAUDE_HOOK_PROFILE:-standard}"
  case "$profile" in
    minimal)
      [[ "$required_level" == "minimal" ]] && return 0
      return 1
      ;;
    standard|strict|"")
      return 0
      ;;
    *)
      return 0  # Unknown profile: run everything
      ;;
  esac
}

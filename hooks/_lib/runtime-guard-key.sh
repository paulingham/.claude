#!/usr/bin/env bash
# Shared key derivation for runtime-guard. Used by record-path AND cleanup-path
# so SubagentStop unambiguously deletes the spawn-side start file.
# Bash-3.2 clean.
#
# Per-class semantic: key derives from subagent_type ONLY. SubagentStop payload
# does NOT reliably expose tool_input.name / tool_input.team_name, so including
# them would produce a different key on cleanup and leak .start files. Trade-off
# accepted: concurrent same-type spawns share one key (first-seen ts wins via
# idempotency in _rg_write_start). Over-cap detection therefore fires when ANY
# instance of the class runs over — conservative, not lossy.

_rg_hasher() {
  if command -v sha1sum >/dev/null 2>&1; then echo "sha1sum"
  elif command -v shasum >/dev/null 2>&1; then echo "shasum"
  else echo ""
  fi
}

_rg_compute_key() {
  local stype="$1" hasher
  hasher=$(_rg_hasher)
  [ -z "$hasher" ] && { printf 'unknown'; return 0; }
  printf '%s' "$stype" | "$hasher" 2>/dev/null | awk '{print $1}'
}

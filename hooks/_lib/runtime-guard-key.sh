#!/usr/bin/env bash
# Shared key derivation for runtime-guard. Used by record-path AND cleanup-path
# to ensure SubagentStop unambiguously deletes the spawn-side start file.
# Bash-3.2 clean.

_rg_compute_key() {
  local stype="$1" name="$2" team="$3"
  local raw="${stype}|${name}|${team}"
  printf '%s' "$raw" | shasum 2>/dev/null | awk '{print $1}'
}

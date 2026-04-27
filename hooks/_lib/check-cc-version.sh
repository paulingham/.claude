#!/usr/bin/env bash
# Warn (non-blocking) when claude --version is below the mcp_tool minimum.
# Exit 0 always: this is advisory, not a gate.
set -u
MIN="2.1.118"
command -v claude >/dev/null 2>&1 || exit 0
ver="$(claude --version 2>/dev/null | awk '{print $2}')"
[ -z "$ver" ] && exit 0
lowest="$(printf '%s\n%s\n' "$ver" "$MIN" | sort -V | head -n1)"
if [ "$lowest" != "$MIN" ] && [ "$ver" != "$MIN" ]; then
  printf 'warning: claude %s < required %s for mcp_tool hooks\n' "$ver" "$MIN" >&2
fi
exit 0

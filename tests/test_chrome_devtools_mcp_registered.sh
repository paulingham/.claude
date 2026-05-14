#!/usr/bin/env bash
# AC1 — settings.json registers chrome-devtools MCP pinned to chrome-devtools-mcp@0.26.0.
# Assertions:
#   - mcpServers["chrome-devtools"] entry exists
#   - args join contains literal "chrome-devtools-mcp@0.26.0"
#   - args join contains NO "@latest" substring
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SETTINGS="$REPO_ROOT/settings.json"

PASS=0; FAIL=0

assert() {
  local label=$1; shift
  if "$@"; then echo "  ok: $label"; PASS=$((PASS + 1))
  else echo "  FAIL: $label"; FAIL=$((FAIL + 1)); fi
}

echo "Test chrome_devtools_mcp_registered"

ARGS_JOINED=$(jq -r '.mcpServers["chrome-devtools"].args | join(" ")' "$SETTINGS" 2>/dev/null || echo "")
COMMAND=$(jq -r '.mcpServers["chrome-devtools"].command' "$SETTINGS" 2>/dev/null || echo "")

assert "mcpServers.chrome-devtools entry present (command field)" \
  test "$COMMAND" = "npx"

assert "args contains literal chrome-devtools-mcp@0.26.0" \
  bash -c "printf '%s' \"$ARGS_JOINED\" | grep -qF 'chrome-devtools-mcp@0.26.0'"

assert "args does NOT contain @latest" \
  bash -c "! printf '%s' \"$ARGS_JOINED\" | grep -qF '@latest'"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

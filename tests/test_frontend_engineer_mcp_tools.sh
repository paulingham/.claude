#!/usr/bin/env bash
# AC2 — agents/frontend-engineer.md tools: allowlist includes the four
# mcp_chrome_devtools_* entries (underscore-flat allowlist form).
# Assertions: each of the four tool names appears in the frontmatter tools: list,
# AND none of them appear in disallowedTools:.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
AGENT="$REPO_ROOT/agents/frontend-engineer.md"

PASS=0; FAIL=0

TOOLS=(
  mcp_chrome_devtools_navigate_page
  mcp_chrome_devtools_list_console_messages
  mcp_chrome_devtools_list_network_requests
  mcp_chrome_devtools_take_screenshot
)

# Extract the frontmatter block (between the first two --- lines).
FRONTMATTER=$(awk '/^---$/{c++; next} c==1' "$AGENT")

# Extract just the tools: list (lines starting with "  - " under "tools:" until next top-level key).
TOOLS_BLOCK=$(printf '%s\n' "$FRONTMATTER" | awk '
  /^tools:/ { in_tools=1; next }
  in_tools && /^[a-zA-Z]/ { in_tools=0 }
  in_tools && /^  - / { print }
')

DISALLOWED_BLOCK=$(printf '%s\n' "$FRONTMATTER" | awk '
  /^disallowedTools:/ { in_dis=1; next }
  in_dis && /^[a-zA-Z]/ { in_dis=0 }
  in_dis && /^  - / { print }
')

echo "Test frontend_engineer_allowlist_includes_chrome_devtools"

for tool in "${TOOLS[@]}"; do
  if printf '%s\n' "$TOOLS_BLOCK" | grep -qE "^  - ${tool}$"; then
    echo "  ok: tools: contains $tool"; PASS=$((PASS + 1))
  else
    echo "  FAIL: tools: missing $tool"; FAIL=$((FAIL + 1))
  fi
  if printf '%s\n' "$DISALLOWED_BLOCK" | grep -qE "^  - ${tool}$"; then
    echo "  FAIL: disallowedTools: must NOT contain $tool"; FAIL=$((FAIL + 1))
  else
    echo "  ok: disallowedTools: clean of $tool"; PASS=$((PASS + 1))
  fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

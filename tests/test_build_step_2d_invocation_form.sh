#!/usr/bin/env bash
# AC11 — Step 2d body uses the **invocation form** for MCP tool names:
#   mcp__chrome-devtools__navigate_page
#   mcp__chrome-devtools__list_console_messages
#   mcp__chrome-devtools__list_network_requests
# (double-underscore + hyphen — server segment matches npm package name).
# The underscore-flat allowlist form `mcp_chrome_devtools_*` MUST NOT appear
# in the Step 2d body (it belongs in agents/*.md frontmatter, not step text).
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"

PASS=0; FAIL=0

STEP_BODY=$(awk '
  /^### Step 2d/ { in_step=1; print; next }
  in_step && /^### Step / { in_step=0 }
  in_step { print }
' "$SKILL")

echo "Test step_2d_uses_invocation_form_with_hyphen"

INVOKE=(
  'mcp__chrome-devtools__navigate_page'
  'mcp__chrome-devtools__list_console_messages'
  'mcp__chrome-devtools__list_network_requests'
)
for tool in "${INVOKE[@]}"; do
  if printf '%s' "$STEP_BODY" | grep -qF "$tool"; then
    echo "  ok: invocation-form tool present: $tool"; PASS=$((PASS + 1))
  else
    echo "  FAIL: invocation-form tool missing: $tool"; FAIL=$((FAIL + 1))
  fi
done

# Allowlist-form tokens (underscore-flat) MUST NOT appear in Step 2d body.
ALLOWLIST=(
  'mcp_chrome_devtools_navigate_page'
  'mcp_chrome_devtools_list_console_messages'
  'mcp_chrome_devtools_list_network_requests'
)
for tool in "${ALLOWLIST[@]}"; do
  if printf '%s' "$STEP_BODY" | grep -qF "$tool"; then
    echo "  FAIL: allowlist-form token MUST NOT appear in Step 2d body: $tool"; FAIL=$((FAIL + 1))
  else
    echo "  ok: allowlist-form absent in step body: $tool"; PASS=$((PASS + 1))
  fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

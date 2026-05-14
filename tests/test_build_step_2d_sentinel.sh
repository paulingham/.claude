#!/usr/bin/env bash
# AC9 — Step 2d body documents sentinel-based escalation:
#   1. First MCP-unavailable failure → DOM_SMOKE_SKIPPED reason=mcp-unavailable-first-run
#      AND touch sentinel `pipeline-state/{task-id}/.dom-smoke-warm`.
#   2. Subsequent invocation with sentinel present AND MCP unavailable →
#      DOM_SMOKE_FAILED reason=mcp-unavailable-after-warm.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"

PASS=0; FAIL=0

STEP_BODY=$(awk '
  /^### Step 2d/ { in_step=1; print; next }
  in_step && /^### Step / { in_step=0 }
  in_step { print }
' "$SKILL")

echo "Test step_2d_sentinel_escalation_documented"

REQUIRED=(
  'pipeline-state/{task-id}/.dom-smoke-warm'
  'mcp-unavailable-first-run'
  'mcp-unavailable-after-warm'
  'DOM_SMOKE_SKIPPED'
  'DOM_SMOKE_FAILED'
)

for token in "${REQUIRED[@]}"; do
  if printf '%s' "$STEP_BODY" | grep -qF "$token"; then
    echo "  ok: token present: $token"; PASS=$((PASS + 1))
  else
    echo "  FAIL: token missing: $token"; FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

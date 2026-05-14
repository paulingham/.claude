#!/usr/bin/env bash
# AC8 — Step 2d body documents `CLAUDE_DOM_SMOKE=0` env-hatch (default ON) and
# the four skip-reason enum values:
#   env-hatch, no-changed-routes, no-route-resolver, mcp-unavailable-first-run
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"

PASS=0; FAIL=0

STEP_BODY=$(awk '
  /^### Step 2d/ { in_step=1; print; next }
  in_step && /^### Step / { in_step=0 }
  in_step { print }
' "$SKILL")

echo "Test step_2d_env_hatch_and_skip_reasons"

if printf '%s' "$STEP_BODY" | grep -qF 'CLAUDE_DOM_SMOKE=0'; then
  echo "  ok: env-hatch CLAUDE_DOM_SMOKE=0 present"; PASS=$((PASS + 1))
else
  echo "  FAIL: env-hatch CLAUDE_DOM_SMOKE=0 missing"; FAIL=$((FAIL + 1))
fi

# Default-ON statement: literal phrase "default ON" or "Default ON" present.
if printf '%s' "$STEP_BODY" | grep -qE '[Dd]efault ON|default-ON'; then
  echo "  ok: default-ON wording present"; PASS=$((PASS + 1))
else
  echo "  FAIL: default-ON wording missing"; FAIL=$((FAIL + 1))
fi

REASONS=(env-hatch no-changed-routes no-route-resolver mcp-unavailable-first-run)
for r in "${REASONS[@]}"; do
  if printf '%s' "$STEP_BODY" | grep -qF "$r"; then
    echo "  ok: skip reason present: $r"; PASS=$((PASS + 1))
  else
    echo "  FAIL: skip reason missing: $r"; FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

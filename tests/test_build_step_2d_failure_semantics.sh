#!/usr/bin/env bash
# AC10 — Step 2d body documents failure semantics:
#   - Console `level: error` → FAIL
#   - Network `status >= 400` → FAIL
#   - Payload schema `{route, errors: [{type, message, url, status}]}`
#   - Inline ignore-regex tokens (eight literal patterns)
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"

PASS=0; FAIL=0

STEP_BODY=$(awk '
  /^### Step 2d/ { in_step=1; print; next }
  in_step && /^### Step / { in_step=0 }
  in_step { print }
' "$SKILL")

echo "Test step_2d_console_and_xhr_failure_rules"

# Failure rule tokens.
RULES=(
  'level: error'
  'status >= 400'
  '{route, errors: [{type, message, url, status}]}'
)
for token in "${RULES[@]}"; do
  if printf '%s' "$STEP_BODY" | grep -qF "$token"; then
    echo "  ok: rule token present: $token"; PASS=$((PASS + 1))
  else
    echo "  FAIL: rule token missing: $token"; FAIL=$((FAIL + 1))
  fi
done

# Ignore-list regex tokens (verbatim).
IGNORES=(
  '^Warning: ReactDOM\.render'
  '^Warning: .* is deprecated'
  '\[HMR\]'
  'Download the React DevTools'
  '\[Fast Refresh\]'
  'Lighthouse'
  '://[^/]*\.(googletagmanager|google-analytics|doubleclick|hotjar)\.'
  'data:'
  'blob:'
)
for token in "${IGNORES[@]}"; do
  if printf '%s' "$STEP_BODY" | grep -qF "$token"; then
    echo "  ok: ignore-regex token present: $token"; PASS=$((PASS + 1))
  else
    echo "  FAIL: ignore-regex token missing: $token"; FAIL=$((FAIL + 1))
  fi
done

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

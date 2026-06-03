#!/usr/bin/env bash
# Security HIGH-4 — Step 2d MUST bind dev server to loopback (127.0.0.1) only.
# Assertions: SKILL.md Step 2d sub-step 5 uses HOST=127.0.0.1 for npm run dev,
# documents framework-specific overrides, and emits DOM_SMOKE_FAILED
# reason=dev-server-non-loopback when binding shows 0.0.0.0. Catalog enum updated.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"
CATALOG="$REPO_ROOT/protocols/verdict-catalog.md"

PASS=0; FAIL=0

assert() {
  local label=$1; shift
  if "$@"; then echo "  ok: $label"; PASS=$((PASS + 1))
  else echo "  FAIL: $label"; FAIL=$((FAIL + 1)); fi
}

echo "Test build_step_2d_loopback_bind"

assert "SKILL.md Step 2d uses HOST=127.0.0.1 npm run dev" \
  grep -qF "HOST=127.0.0.1 setsid npm run dev" "$SKILL"

assert "SKILL.md Step 2d documents framework-specific loopback overrides" \
  grep -qF "NITRO_HOST=127.0.0.1" "$SKILL"

assert "SKILL.md Step 2d emits DOM_SMOKE_FAILED reason=dev-server-non-loopback" \
  grep -qF "DOM_SMOKE_FAILED reason=dev-server-non-loopback" "$SKILL"

assert "SKILL.md Step 2d health poll uses 127.0.0.1" \
  grep -qF "http://127.0.0.1:3000/" "$SKILL"

assert "verdict catalog DOM_SMOKE_FAILED row lists dev-server-non-loopback" \
  bash -c "grep '^| \`DOM_SMOKE_FAILED\`' '$CATALOG' | grep -qF 'dev-server-non-loopback'"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

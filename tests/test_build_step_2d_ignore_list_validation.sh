#!/usr/bin/env bash
# Security HIGH-3 — Step 2d MUST validate ignore-list patterns and reject overbroad neuters.
# Assertions: SKILL.md Step 2d contains a validation paragraph naming an overbroad-pattern
# rejection regex, and DOM_SMOKE_FAILED reason enum in verdict catalog includes
# ignore-list-overbroad.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"
CATALOG="$REPO_ROOT/rules/verdict-catalog.md"

PASS=0; FAIL=0

assert() {
  local label=$1; shift
  if "$@"; then echo "  ok: $label"; PASS=$((PASS + 1))
  else echo "  FAIL: $label"; FAIL=$((FAIL + 1)); fi
}

echo "Test build_step_2d_ignore_list_validation"

assert "SKILL.md Step 2d contains 'Validate ignore-list patterns' paragraph" \
  grep -qF "Validate ignore-list patterns" "$SKILL"

assert "SKILL.md Step 2d contains overbroad-neuter rejection regex" \
  grep -qF '^(\.\*|\.\+|\^|\$|\.|)$' "$SKILL"

assert "SKILL.md emits DOM_SMOKE_FAILED reason=ignore-list-overbroad" \
  grep -qF "DOM_SMOKE_FAILED reason=ignore-list-overbroad" "$SKILL"

assert "verdict catalog DOM_SMOKE_FAILED row lists ignore-list-overbroad" \
  bash -c "grep '^| \`DOM_SMOKE_FAILED\`' '$CATALOG' | grep -qF 'ignore-list-overbroad'"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

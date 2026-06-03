#!/usr/bin/env bash
# AC3 — protocols/verdict-catalog.md contains three DOM_SMOKE_* rows with correct
# polarities and emitter `build-implementation`, plus a one-liner under ## Notes
# linking back to build-implementation Step 2d.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CATALOG="$REPO_ROOT/protocols/verdict-catalog.md"

PASS=0; FAIL=0

assert_row() {
  local verdict=$1 polarity=$2 label=$3
  # Match a catalog table row: starts with | `VERDICT` | polarity | `build-implementation` | build | ...
  local pattern="^\\| \`${verdict}\` \\| ${polarity} \\| \`build-implementation\` \\| build \\|"
  if grep -qE "$pattern" "$CATALOG"; then
    echo "  ok: $label"; PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (pattern: $pattern)"; FAIL=$((FAIL + 1))
  fi
}

echo "Test three_dom_smoke_verdicts_declared"

assert_row "DOM_SMOKE_PASSED" "success" "DOM_SMOKE_PASSED row (success, build-implementation, build)"
assert_row "DOM_SMOKE_SKIPPED" "info" "DOM_SMOKE_SKIPPED row (info, build-implementation, build)"
assert_row "DOM_SMOKE_FAILED" "failure" "DOM_SMOKE_FAILED row (failure, build-implementation, build)"

# Notes section must reference DOM_SMOKE_* and Step 2d.
NOTES_BODY=$(awk '/^## Notes/{f=1; next} f' "$CATALOG")
if printf '%s' "$NOTES_BODY" | grep -qF "DOM_SMOKE_" \
   && printf '%s' "$NOTES_BODY" | grep -qF "Step 2d"; then
  echo "  ok: ## Notes references DOM_SMOKE_* and Step 2d"; PASS=$((PASS + 1))
else
  echo "  FAIL: ## Notes missing DOM_SMOKE_*/Step 2d one-liner"; FAIL=$((FAIL + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

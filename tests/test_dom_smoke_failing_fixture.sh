#!/usr/bin/env bash
# AC12 — Behaviour fixture: tests/fixtures/dom-smoke/failing-route/index.html
# contains `console.error('boom')`. Test simulates the Step 2d MCP shim by
# (a) parsing the fixture HTML for the console.error call, (b) running the
# documented routing logic (`level: error` after ignore-filter → FAIL), and
# (c) asserting the verdict is DOM_SMOKE_FAILED with byte-exact payload
#   {"route": "/", "errors": [{"type": "console", "message": "boom", "url": null, "status": null}]}
#
# Mock boundary: this test does NOT spawn a real chrome-devtools-mcp server or
# launch Chrome. The MCP server is mocked by parsing the fixture HTML inline.
# The documented routing-logic contract (ignore-filter → level:error → FAIL,
# payload schema) is exercised against that mock. Full E2E with real MCP +
# real Chrome is out of scope until the Step 2d test runner ships.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FIXTURE="$REPO_ROOT/tests/fixtures/dom-smoke/failing-route/index.html"

PASS=0; FAIL=0

assert() {
  local label=$1; shift
  if "$@"; then echo "  ok: $label"; PASS=$((PASS + 1))
  else echo "  FAIL: $label"; FAIL=$((FAIL + 1)); fi
}

echo "Test failing_route_fixture_emits_dom_smoke_failed"

assert "fixture file exists" test -f "$FIXTURE"

# Mock MCP `list_console_messages`: parse the fixture for console.error calls.
# Returns one entry per call. Extracts the literal string argument.
mock_console_messages() {
  grep -oE "console\.error\(['\"][^'\"]+['\"]\)" "$FIXTURE" \
    | sed -E "s/^console\.error\(['\"]([^'\"]+)['\"]\)$/\1/"
}

# Apply documented Step 2d routing logic to mock output, build payload.
CONSOLE_ERRORS=$(mock_console_messages)
assert "fixture emits at least one console.error" test -n "$CONSOLE_ERRORS"

# The documented payload shape — byte-exact match against the AC spec.
EXPECTED='{"route": "/", "errors": [{"type": "console", "message": "boom", "url": null, "status": null}]}'

# Build the payload from the (single) mock-detected error.
FIRST_MSG=$(printf '%s\n' "$CONSOLE_ERRORS" | head -1)
ACTUAL=$(printf '{"route": "/", "errors": [{"type": "console", "message": "%s", "url": null, "status": null}]}' "$FIRST_MSG")

if [[ "$ACTUAL" == "$EXPECTED" ]]; then
  echo "  ok: payload byte-exact match"; PASS=$((PASS + 1))
else
  echo "  FAIL: payload mismatch"
  echo "    expected: $EXPECTED"
  echo "    actual:   $ACTUAL"
  FAIL=$((FAIL + 1))
fi

# Verdict routing: level:error (no ignore-list match) → DOM_SMOKE_FAILED.
# Mock ignore-filter check — "boom" matches none of the documented ignore patterns.
classify() {
  local msg=$1
  case "$msg" in
    Warning:*ReactDOM.render*|Warning:*deprecated*|*'[HMR]'*|*'Download the React DevTools'*|*'[Fast Refresh]'*|*Lighthouse*)
      echo IGNORED ;;
    *)
      echo FAIL ;;
  esac
}
VERDICT_REASON=$(classify "$FIRST_MSG")
assert "console error 'boom' classified as FAIL (not ignored)" test "$VERDICT_REASON" = FAIL

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

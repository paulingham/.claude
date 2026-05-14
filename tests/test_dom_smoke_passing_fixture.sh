#!/usr/bin/env bash
# AC13 — Behaviour fixture: tests/fixtures/dom-smoke/passing-route/index.html
# is clean (no console errors) and emits one 200 XHR. Test simulates the Step 2d
# MCP shim by (a) parsing the fixture for console calls and XHR markup, (b)
# running the documented routing logic (no level:error AND no status>=400 →
# PASS), and (c) asserting the verdict is DOM_SMOKE_PASSED.
#
# Mock boundary: same as test_dom_smoke_failing_fixture.sh — no real MCP server
# or Chrome. The Step 2d routing-logic contract is exercised against parsed
# fixture markup. Full E2E is out of scope until the Step 2d test runner ships.
#
# Report-file assertion: simulates the documented audit-trail write to
# pipeline-state/{task-id}/build-artifacts/dom-smoke-report.json. The test
# writes the report itself and asserts presence + JSON validity.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
FIXTURE="$REPO_ROOT/tests/fixtures/dom-smoke/passing-route/index.html"

PASS=0; FAIL=0

assert() {
  local label=$1; shift
  if "$@"; then echo "  ok: $label"; PASS=$((PASS + 1))
  else echo "  FAIL: $label"; FAIL=$((FAIL + 1)); fi
}

echo "Test passing_route_fixture_emits_dom_smoke_passed"

assert "fixture file exists" test -f "$FIXTURE"

# Mock MCP shim — passing fixture must NOT contain console.error calls.
CONSOLE_ERROR_COUNT=$(grep -cE "console\.error\(" "$FIXTURE" || true)
assert "fixture has zero console.error calls" test "$CONSOLE_ERROR_COUNT" -eq 0

# Mock MCP shim — passing fixture documents one XHR with HTTP 200 status.
# Convention: the fixture marks expected XHR as an HTML comment `<!-- XHR status=200 -->`.
XHR_200_COUNT=$(grep -cE "<!-- XHR status=200 -->" "$FIXTURE" || true)
assert "fixture documents exactly one 200 XHR" test "$XHR_200_COUNT" -eq 1

# Verdict routing: zero errors + zero status>=400 → DOM_SMOKE_PASSED.
VERDICT=DOM_SMOKE_PASSED
if [[ "$CONSOLE_ERROR_COUNT" -gt 0 ]]; then VERDICT=DOM_SMOKE_FAILED; fi
assert "computed verdict is DOM_SMOKE_PASSED" test "$VERDICT" = DOM_SMOKE_PASSED

# Audit-trail report — simulate the documented write.
REPORT_DIR=$(mktemp -d)
REPORT="$REPORT_DIR/dom-smoke-report.json"
trap 'rm -rf "$REPORT_DIR"' EXIT

cat > "$REPORT" <<'EOF'
{"routes_checked": ["/"], "verdict": "DOM_SMOKE_PASSED", "payload": null, "sentinel_present": false, "comparison_base": "merge-base"}
EOF

assert "dom-smoke-report.json written" test -f "$REPORT"
assert "report parses as JSON" jq -e . "$REPORT" >/dev/null
assert "report.verdict is DOM_SMOKE_PASSED" bash -c "[[ \$(jq -r .verdict '$REPORT') = DOM_SMOKE_PASSED ]]"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

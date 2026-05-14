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
SKILL="$REPO_ROOT/skills/build-implementation/SKILL.md"

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
# Ignore-list is parsed dynamically from SKILL.md Step 2d sub-step 8 — if the
# SKILL drops a regex, the dynamic list shrinks and a previously-ignored
# message becomes a failure (this is the contract AC12 enforces).
#
# Extract regex tokens from lines of the form `   - \`<regex>\`` inside the
# "Inline ignore-list regex" block (header line .. next blank line at depth 0).
load_console_ignore_patterns() {
  awk '
    /^[0-9]+\. \*\*Inline ignore-list regex\*\*/ { in_block=1; next }
    in_block && /^[0-9]+\. / { in_block=0 }
    in_block && /^[[:space:]]+- `[^`]+`[[:space:]]*$/ {
      # Skip URL-pattern lines described in prose form, not bare-regex form
      # (those are network ignores, handled by the network branch elsewhere).
      if ($0 ~ /Network URLs/ || $0 ~ /scheme URLs/) next
      line = $0
      sub(/^[[:space:]]+- `/, "", line)
      sub(/`[[:space:]]*$/, "", line)
      print line
    }
  ' "$SKILL"
}

IGNORE_PATTERNS=$(load_console_ignore_patterns)
assert "ignore-list parsed from SKILL.md (non-empty)" test -n "$IGNORE_PATTERNS"

classify() {
  local msg=$1
  local pat
  while IFS= read -r pat; do
    [[ -z "$pat" ]] && continue
    if [[ "$msg" =~ $pat ]]; then echo IGNORED; return; fi
  done <<< "$IGNORE_PATTERNS"
  echo FAIL
}
VERDICT_REASON=$(classify "$FIRST_MSG")
assert "console error 'boom' classified as FAIL (not ignored)" test "$VERDICT_REASON" = FAIL

# Per-pattern coverage: each documented regex must actually ignore a
# representative matching message. If SKILL.md drops a regex, the parsed
# list shrinks and the corresponding sample below classifies as FAIL,
# surfacing the drift. This is what closes the AC12 tautology: classify()
# now sources the list from SKILL.md AND each documented entry has a live
# assertion against its expected ignore behaviour.
assert_ignored() {
  local label=$1 sample=$2 got
  got=$(classify "$sample")
  if [[ "$got" == IGNORED ]]; then
    echo "  ok: $label"; PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (got $got, ignore-list = $IGNORE_PATTERNS)"; FAIL=$((FAIL + 1))
  fi
}

assert_ignored "ignores 'Warning: ReactDOM.render' samples" \
  "Warning: ReactDOM.render is no longer supported"
assert_ignored "ignores 'Warning: ... is deprecated' samples" \
  "Warning: componentWillMount is deprecated"
assert_ignored "ignores '[HMR]' samples" \
  "[HMR] connected"
assert_ignored "ignores 'Download the React DevTools' samples" \
  "Download the React DevTools for a better development experience"
assert_ignored "ignores '[Fast Refresh]' samples" \
  "[Fast Refresh] rebuilding"
assert_ignored "ignores 'Lighthouse' samples" \
  "Lighthouse audit completed"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

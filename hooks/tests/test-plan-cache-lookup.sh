#!/usr/bin/env bash
# Test harness for _plan_cache_write_resume_stub in hooks/_lib/plan-cache-lookup.sh.
#
# Covers:
#   AC-B5a: stub writes to $HARNESS_DATA/pipeline-state/{task}/architect-context.md
#           when HARNESS_DATA is explicitly set
#   AC-B5b: self-resolving fallback: when HARNESS_DATA is unset, resolves via
#           ${CLAUDE_CONFIG_DIR:-$HOME/.claude} (CORRECTION from validation round 3)
#
# Run from any directory:
#   bash hooks/tests/test-plan-cache-lookup.sh
# Exit 0 = all pass, 1 = any failure.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLAN_CACHE_LIB="$HOOKS_DIR/_lib/plan-cache-lookup.sh"

PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

echo "=== plan-cache-lookup _plan_cache_write_resume_stub Test Harness ==="
echo ""

# ---------------------------------------------------------------------------
# AC-B5a: stub writes to HARNESS_DATA path when HARNESS_DATA is explicitly set
# ---------------------------------------------------------------------------
echo "-- AC-B5a: stub file lands at HARNESS_DATA/pipeline-state/{task}/architect-context.md --"

B5A_TMP=$(mktemp -d)
trap 'rm -rf "$B5A_TMP"' EXIT

(
  export HARNESS_DATA="${B5A_TMP}/harness"
  # Source the plan-cache-lookup lib (sources the public API functions only)
  # We need a partial source: only _plan_cache_write_resume_stub
  source "$PLAN_CACHE_LIB"
  _plan_cache_write_resume_stub "my-task-id"
)
B5A_STUB="${B5A_TMP}/harness/pipeline-state/my-task-id/architect-context.md"
if [[ -f "$B5A_STUB" ]]; then
  pass "AC-B5a: stub created at HARNESS_DATA/pipeline-state/my-task-id/architect-context.md"
else
  fail "AC-B5a: stub created at HARNESS_DATA path" "file exists" "absent (got: $(find "${B5A_TMP}" -name '*.md' 2>/dev/null || echo 'none'))"
fi

# Verify stub contents
if [[ -f "$B5A_STUB" ]] && grep -q 'cache_hit: true' "$B5A_STUB"; then
  pass "AC-B5a: stub contents contain cache_hit: true marker"
else
  fail "AC-B5a: stub contents contain cache_hit: true marker" "cache_hit: true in file" "absent"
fi

echo ""

# ---------------------------------------------------------------------------
# AC-B5b: self-resolving fallback when HARNESS_DATA is unset
# Verifies: function resolves HARNESS_DATA from CLAUDE_CONFIG_DIR when unset
# ---------------------------------------------------------------------------
echo "-- AC-B5b: self-resolving fallback: HARNESS_DATA unset → resolves from CLAUDE_CONFIG_DIR --"

B5B_TMP=$(mktemp -d)

(
  unset HARNESS_DATA
  export CLAUDE_CONFIG_DIR="${B5B_TMP}/config"
  unset CLAUDE_PLUGIN_DATA
  source "$PLAN_CACHE_LIB"
  _plan_cache_write_resume_stub "fallback-task"
)
B5B_STUB="${B5B_TMP}/config/pipeline-state/fallback-task/architect-context.md"
if [[ -f "$B5B_STUB" ]]; then
  pass "AC-B5b: stub created at CLAUDE_CONFIG_DIR/pipeline-state/fallback-task/architect-context.md"
else
  fail "AC-B5b: stub created via CLAUDE_CONFIG_DIR fallback" "file exists" "absent (find: $(find "${B5B_TMP}" -name '*.md' 2>/dev/null | head -5 || echo 'none'))"
fi

rm -rf "$B5B_TMP"

echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "=== Results: $PASS passed, $FAIL failed ==="
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo "Some tests failed."
  exit 1
fi

echo "All tests passed."
exit 0

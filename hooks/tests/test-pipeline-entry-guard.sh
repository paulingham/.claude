#!/usr/bin/env bash
# Tests for pipeline-entry-guard.sh block path — slice-3 integration tests.
#
# Exercises the block path by synthesizing absent-signal context:
#   - CLAUDE_PIPELINE_TASK_ID unset
#   - HARNESS_DATA pointed at temp dir (no active pipeline files)
#   - role = software-engineer (gated role)
#
# The block path writes pipeline-entry-advisory.jsonl via the Python CLI.
# This test validates:
#   1. advisory JSONL written with action:"would_block"
#   2. shell hook exits 0 (advisory mode invariant)
#   3. non-gated role (architect) -> allow, no ledger write
#
# NOTE: Synthetic records written by this test do NOT count toward the N=10
#       promotion criterion. Promotion remains data-blocked post-merge.
#
# Run from repo root: bash hooks/tests/test-pipeline-entry-guard.sh
# Exit 0 if all pass, exit 1 if any fail.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$((FAIL + 1)); }

run_test() {
  local name="$1"
  local expected_exit="$2"
  local actual_exit="$3"
  if [[ "$actual_exit" -eq "$expected_exit" ]]; then
    pass "$name"
  else
    fail "$name" "$expected_exit" "$actual_exit"
  fi
}

echo "=== pipeline-entry-guard (block path) Integration Test Harness ==="
echo ""

# -- Syntax check -------------------------------------------------------------
echo "-- syntax --"
bash -n "$HOOKS_DIR/pipeline-entry-guard.sh" > /dev/null 2>&1
run_test "syntax valid" 0 $?

# -- Python availability check -------------------------------------------------
if ! command -v python3 > /dev/null 2>&1; then
  echo "SKIP: python3 not available"
  exit 0
fi

# -- Setup hermetic temp HARNESS_DATA -----------------------------------------
PEG_TMP=$(mktemp -d)
PEG_SESSION="peg-test-$$"

run_peg() {
  # $1 = role (subagent_type)
  local role="$1"
  (
    # Hermetic: no active pipeline, no task ID
    export HARNESS_DATA="$PEG_TMP"
    export CLAUDE_PLUGIN_DATA="$PEG_TMP"
    export CLAUDE_SESSION_ID="$PEG_SESSION"
    unset CLAUDE_PIPELINE_TASK_ID 2>/dev/null || true
    unset CLAUDE_WORKSTREAM 2>/dev/null || true
    # Ensure hook-profile runs as "standard" (not minimal-only)
    export CLAUDE_HOOK_PROFILE=standard
    jq -nc --arg role "$role" \
      '{tool_name:"Agent",tool_input:{subagent_type:$role},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/pipeline-entry-guard.sh" 2>/dev/null
  )
}

# -- AC-3.1: block path writes pipeline-entry-advisory.jsonl ------------------
echo "-- block path advisory write --"

run_peg "software-engineer"
ACTUAL_EXIT=$?
run_test "advisory: block exits 0 (shell hook advisory-mode invariant)" 0 "$ACTUAL_EXIT"

# Check that advisory JSONL was written with action:"would_block"
ADVISORY_JSONL=$(find "$PEG_TMP" -name "pipeline-entry-advisory.jsonl" 2>/dev/null | head -1)
if [[ -n "$ADVISORY_JSONL" ]] && grep -qE '"action"[[:space:]]*:[[:space:]]*"would_block"' "$ADVISORY_JSONL" 2>/dev/null; then
  pass "advisory: block path writes pipeline-entry-advisory.jsonl"
else
  fail "advisory: block path writes pipeline-entry-advisory.jsonl" \
    "pipeline-entry-advisory.jsonl with action:would_block" \
    "not found (ADVISORY_JSONL=${ADVISORY_JSONL:-missing})"
fi

# -- AC-3.1: non-gated role -> allow, no advisory write -----------------------
echo "-- non-gated role --"

# Remove existing advisory file to test fresh
rm -f "$ADVISORY_JSONL" 2>/dev/null || true
rm -rf "$PEG_TMP/metrics" 2>/dev/null || true
mkdir -p "$PEG_TMP"

run_peg "architect"
ARCH_EXIT=$?
run_test "advisory: non-gated role (architect) -> exits 0" 0 "$ARCH_EXIT"

# No ledger write for non-gated role
ARCH_ADVISORY=$(find "$PEG_TMP" -name "pipeline-entry-advisory.jsonl" 2>/dev/null | head -1)
if [[ -n "$ARCH_ADVISORY" ]] && grep -q '"action"' "$ARCH_ADVISORY" 2>/dev/null; then
  fail "advisory: non-gated role with no signals -> allow, no ledger write" \
    "no ledger write" "ledger written"
else
  pass "advisory: non-gated role with no signals -> allow, no ledger write"
fi

# -- Cleanup ------------------------------------------------------------------
rm -rf "$PEG_TMP"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0

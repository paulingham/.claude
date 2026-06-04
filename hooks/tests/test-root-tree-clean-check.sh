#!/usr/bin/env bash
# Tests for root-tree-clean-check.sh (Stop + SessionEnd)
# Asserts root-tree cleanliness against a session-start snapshot.
# Also tests root-snapshot-capture.sh (SessionStart companion).
#
# Run from repo root: bash hooks/tests/test-root-tree-clean-check.sh
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

echo "=== root-tree-clean-check + root-snapshot-capture Test Harness ==="
echo ""

# -- Syntax checks ------------------------------------------------------------
echo "-- syntax --"
bash -n "$HOOKS_DIR/root-tree-clean-check.sh" > /dev/null 2>&1
run_test "root-tree-clean-check: syntax valid" 0 $?

bash -n "$HOOKS_DIR/root-snapshot-capture.sh" > /dev/null 2>&1
run_test "root-snapshot-capture: syntax valid" 0 $?

# Build hermetic scratch git repo
RCC_TMP=$(mktemp -d)
RCC_REPO="$RCC_TMP/repo"
git init -q "$RCC_REPO" 2>/dev/null
(cd "$RCC_REPO" && git commit -q --allow-empty -m init 2>/dev/null)
echo "hello" > "$RCC_REPO/tracked.py"
(cd "$RCC_REPO" && git add tracked.py && git commit -q -m "seed tracked.py" 2>/dev/null)

# Hermetic HARNESS_DATA so snapshots go to a temp dir, not real ~/.claude
RCC_DATA="$RCC_TMP/data"
mkdir -p "$RCC_DATA"

# ---------------------------------------------------------------------------
# root-snapshot-capture tests
# ---------------------------------------------------------------------------
echo "-- root-snapshot-capture --"

# Run capture in the clean repo
(cd "$RCC_REPO" && \
  CLAUDE_PLUGIN_DATA="$RCC_DATA" CLAUDE_SESSION_ID="rcc-test-1" \
  bash "$HOOKS_DIR/root-snapshot-capture.sh" > /dev/null 2>&1)
run_test "capture exits 0 on clean repo" 0 $?

# Snapshot file should exist under HARNESS_DATA
SNAP_FILE="$RCC_DATA/root-snapshots/rcc-test-1.txt"
if [[ -f "$SNAP_FILE" ]]; then
  pass "capture: snapshot file created at HARNESS_DATA"
else
  fail "capture: snapshot file created at HARNESS_DATA" "file exists" "not found at $SNAP_FILE"
fi

# Snapshot should be empty (clean repo = no porcelain output)
SNAP_CONTENT=$(grep -v '^#' "$SNAP_FILE" 2>/dev/null | tr -d '[:space:]')
if [[ -z "$SNAP_CONTENT" ]]; then
  pass "capture: clean repo snapshot is empty (no dirty files)"
else
  fail "capture: clean repo snapshot is empty" "empty" "got: $SNAP_CONTENT"
fi

# Snapshot file must NOT be under REPO_ROOT
if [[ "$SNAP_FILE" == "$RCC_REPO/"* ]]; then
  fail "capture: snapshot not under REPO_ROOT" "outside repo" "inside repo"
else
  pass "capture: snapshot stored outside REPO_ROOT"
fi

# Idempotent: second capture overwrites (no duplicate accumulation)
(cd "$RCC_REPO" && \
  CLAUDE_PLUGIN_DATA="$RCC_DATA" CLAUDE_SESSION_ID="rcc-test-1" \
  bash "$HOOKS_DIR/root-snapshot-capture.sh" > /dev/null 2>&1)
SNAP_COUNT=$(find "$RCC_DATA/root-snapshots" -name "rcc-test-1*" 2>/dev/null | wc -l | tr -d ' ')
if [[ "$SNAP_COUNT" -le 1 ]]; then
  pass "capture: idempotent (no duplicate snapshot files)"
else
  fail "capture: idempotent (no duplicate snapshot files)" "1" "$SNAP_COUNT"
fi

# ---------------------------------------------------------------------------
# root-tree-clean-check tests (no drift)
# ---------------------------------------------------------------------------
echo "-- root-tree-clean-check: clean repo (no drift) --"

# Check against the existing clean snapshot -> should be silent, exit 0
(cd "$RCC_REPO" && \
  CLAUDE_PLUGIN_DATA="$RCC_DATA" CLAUDE_SESSION_ID="rcc-test-1" \
  bash "$HOOKS_DIR/root-tree-clean-check.sh" > /dev/null 2>&1)
run_test "clean check: clean repo against clean snapshot -> exit 0" 0 $?

# Check output is silent when clean
CLEAN_OUT=$(
  cd "$RCC_REPO" && \
  CLAUDE_PLUGIN_DATA="$RCC_DATA" CLAUDE_SESSION_ID="rcc-test-1" \
  bash "$HOOKS_DIR/root-tree-clean-check.sh" 2>&1
)
if [[ -z "${CLEAN_OUT// /}" ]]; then
  pass "clean check: silent when no drift"
else
  fail "clean check: silent when no drift" "empty output" "got: $CLEAN_OUT"
fi

# No snapshot file -> silent exit 0 (first session, nothing to compare)
(cd "$RCC_REPO" && \
  CLAUDE_PLUGIN_DATA="$RCC_DATA" CLAUDE_SESSION_ID="rcc-test-no-snap" \
  bash "$HOOKS_DIR/root-tree-clean-check.sh" > /dev/null 2>&1)
run_test "clean check: no snapshot yet -> exit 0 (first session)" 0 $?

# ---------------------------------------------------------------------------
# root-tree-clean-check tests (drift detected)
# ---------------------------------------------------------------------------
echo "-- root-tree-clean-check: drift detected --"

# Capture clean snapshot
(cd "$RCC_REPO" && \
  CLAUDE_PLUGIN_DATA="$RCC_DATA" CLAUDE_SESSION_ID="rcc-drift-1" \
  bash "$HOOKS_DIR/root-snapshot-capture.sh" > /dev/null 2>&1)

# Now dirty the tree (modify tracked.py without staging)
echo "mutation" >> "$RCC_REPO/tracked.py"

# Check should detect drift, emit LOUD warning, exit 0 (non-blocking advisory)
DRIFT_OUT=$(
  cd "$RCC_REPO" && \
  CLAUDE_PLUGIN_DATA="$RCC_DATA" CLAUDE_SESSION_ID="rcc-drift-1" \
  bash "$HOOKS_DIR/root-tree-clean-check.sh" 2>&1
)
DRIFT_EXIT=$?
run_test "drift check: dirty repo -> exit 0 (advisory)" 0 $DRIFT_EXIT

# Warning must be LOUD (contain uppercase WARNING or DRIFT or similar)
if echo "$DRIFT_OUT" | grep -qiE "warning|drift|contamination|dirty"; then
  pass "drift check: loud warning emitted on drift"
else
  fail "drift check: loud warning emitted on drift" "WARNING/DRIFT present" "missing"
fi

# Warning must name the drifted file
if echo "$DRIFT_OUT" | grep -q "tracked.py"; then
  pass "drift check: warning names the drifted file"
else
  fail "drift check: warning names the drifted file" "tracked.py present" "missing"
fi

# Forensics diff must be preserved under ~/.claude/forensics (uses real HOME or HARNESS_DATA)
# The hook should write to $HARNESS_DATA/forensics/ (or $HOME/.claude/forensics/)
FORENSICS_DIR="$RCC_DATA/forensics"
FORENSICS_FILE_COUNT=$(find "$FORENSICS_DIR" -name "root-drift-*.diff" 2>/dev/null | wc -l | tr -d ' ')
if [[ "$FORENSICS_FILE_COUNT" -gt 0 ]]; then
  pass "drift check: forensics diff preserved under HARNESS_DATA/forensics/"
else
  # Also check real ~/.claude/forensics in case hook uses HOME resolution
  FORENSICS_FILE_COUNT2=$(find "$HOME/.claude/forensics" -name "root-drift-*.diff" 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$FORENSICS_FILE_COUNT2" -gt 0 ]]; then
    pass "drift check: forensics diff preserved under ~/.claude/forensics/"
  else
    fail "drift check: forensics diff preserved" "root-drift-*.diff exists" "not found in $FORENSICS_DIR or ~/.claude/forensics/"
  fi
fi

# Must NOT auto-revert (dirty file must still be dirty)
STILL_DIRTY=$(cd "$RCC_REPO" && git status --porcelain 2>/dev/null)
if echo "$STILL_DIRTY" | grep -q "tracked.py"; then
  pass "drift check: does NOT auto-revert dirty file"
else
  fail "drift check: does NOT auto-revert dirty file" "still dirty" "reverted or missing"
fi

# Restore clean state for subsequent tests
git -C "$RCC_REPO" checkout -- tracked.py 2>/dev/null

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
rm -rf "$RCC_TMP"
# Remove forensics test artifacts from real ~/.claude/forensics if created there
find "$HOME/.claude/forensics" -name "root-drift-*" -newer /tmp -delete 2>/dev/null || true

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0

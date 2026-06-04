#!/usr/bin/env bash
# Test harness for scripts/detect-stale-pipeline-state.sh --prune guard.
#
# Covers:
#   GAP-2: detect-stale prune guard — HARNESS_STATE_DIR included in safe-rm check.
#     When a flat legacy pipeline file lives directly under HARNESS_STATE_DIR
#     (e.g. $HARNESS_STATE_DIR/my-task-pipeline.md), the --prune output must be
#     "rm <file>" and NEVER "rm -rf <HARNESS_STATE_DIR>".
#     Without the guard, `dir=$(dirname $f) == $HARNESS_STATE_DIR` falls through to
#     `rm -rf $dir` which would wipe the entire HARNESS_DATA pipeline-state tree.
#
# NOTE: detect-stale-pipeline-state.sh uses `mapfile` (bash 4+). On macOS with
# bash 3.2, the full script cannot execute. These tests therefore test the prune
# guard logic (lines 106-112) directly in isolated subshells, not the full script.
# This is correct: the GAP is specifically in the guard predicate, not in find/mapfile.
# The RED proof simulates guard removal by running the prune block without the
# HARNESS_STATE_DIR clause.
#
# Run from any directory:
#   bash hooks/tests/test-detect-stale-pipeline-state.sh
# Exit 0 = all pass, 1 = any failure.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DETECT_STALE="${SCRIPT_DIR}/../../scripts/detect-stale-pipeline-state.sh"

PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

echo "=== detect-stale-pipeline-state.sh --prune guard Test Harness ==="
echo ""

PRUNE_TMP=$(mktemp -d)
trap 'rm -rf "$PRUNE_TMP"' EXIT

FAKE_HARNESS_STATE="${PRUNE_TMP}/harness/pipeline-state"
FAKE_REPO_STATE="${PRUNE_TMP}/repo/pipeline-state"
mkdir -p "$FAKE_HARNESS_STATE" "$FAKE_REPO_STATE"

# ---------------------------------------------------------------------------
# GAP-2a: flat file under HARNESS_STATE_DIR → guard emits "rm <file>"
#
# Simulates: STALE_PATHS=("$HARNESS_STATE_DIR/task-pipeline.md")
# Runs the prune block directly (the 6 lines from detect-stale lines 106-112).
# ---------------------------------------------------------------------------
echo "-- GAP-2a: flat HARNESS_STATE_DIR file → 'rm <file>' (not 'rm -rf <dir>') --"

FLAT_FILE="${FAKE_HARNESS_STATE}/prune-test-task-pipeline.md"
printf 'fixture\n' > "$FLAT_FILE"

# Run the exact prune guard logic from detect-stale lines 108-111 in a subshell
PRUNE_OUT=$(
  STATE_DIR="$FAKE_REPO_STATE"
  HARNESS_STATE_DIR="$FAKE_HARNESS_STATE"
  STALE_PATHS=("$FLAT_FILE")
  for f in "${STALE_PATHS[@]}"; do
    dir="$(dirname "$f")"
    if [[ "$dir" == "$STATE_DIR" || "$dir" == "$HARNESS_STATE_DIR" ]]; then
      echo "rm $f"
    else
      echo "rm -rf $dir"
    fi
  done
)

if echo "$PRUNE_OUT" | grep -qF "rm ${FLAT_FILE}"; then
  pass "GAP-2a: prune guard emits 'rm ${FLAT_FILE}' for flat HARNESS_STATE_DIR file"
else
  fail "GAP-2a: prune guard emits safe rm" "rm ${FLAT_FILE}" \
    "$(echo "$PRUNE_OUT" | head -3 || echo '(empty)')"
fi

# Use -xF (exact whole-line match) to avoid false positive from a subdir path
if echo "$PRUNE_OUT" | grep -qxF "rm -rf ${FAKE_HARNESS_STATE}"; then
  fail "GAP-2a: prune guard must NOT emit 'rm -rf ${FAKE_HARNESS_STATE}'" \
    "absent" "present (would wipe HARNESS_DATA pipeline-state tree)"
else
  pass "GAP-2a: prune guard does NOT emit 'rm -rf ${FAKE_HARNESS_STATE}'"
fi

echo ""

# ---------------------------------------------------------------------------
# GAP-2b: task-subdir file → guard emits "rm -rf <task-subdir>" (correct, safe)
# dir=$(dirname .../task-id/pipeline.md) = .../task-id ≠ HARNESS_STATE_DIR
# so falls to the else branch → "rm -rf .../task-id" (removes task dir only)
# ---------------------------------------------------------------------------
echo "-- GAP-2b: task-subdir file → 'rm -rf <task-subdir>' (correct) --"

TASK_SUBDIR="${FAKE_HARNESS_STATE}/prune-subdir-task"
mkdir -p "$TASK_SUBDIR"
SUBDIR_FILE="${TASK_SUBDIR}/pipeline.md"
printf 'fixture\n' > "$SUBDIR_FILE"

PRUNE_OUT2=$(
  STATE_DIR="$FAKE_REPO_STATE"
  HARNESS_STATE_DIR="$FAKE_HARNESS_STATE"
  STALE_PATHS=("$SUBDIR_FILE")
  for f in "${STALE_PATHS[@]}"; do
    dir="$(dirname "$f")"
    if [[ "$dir" == "$STATE_DIR" || "$dir" == "$HARNESS_STATE_DIR" ]]; then
      echo "rm $f"
    else
      echo "rm -rf $dir"
    fi
  done
)

if echo "$PRUNE_OUT2" | grep -qF "rm -rf ${TASK_SUBDIR}"; then
  pass "GAP-2b: prune guard emits 'rm -rf ${TASK_SUBDIR}' for task-subdir file"
else
  fail "GAP-2b: prune guard emits rm -rf for task-subdir" \
    "rm -rf ${TASK_SUBDIR}" "$(echo "$PRUNE_OUT2" | head -3 || echo '(empty)')"
fi

# Use grep -xF to match exact whole-line: "rm -rf <HARNESS_STATE_DIR>" with nothing after
# (prevents false positive from "rm -rf <HARNESS_STATE_DIR>/<subdir>" matching)
if echo "$PRUNE_OUT2" | grep -qxF "rm -rf ${FAKE_HARNESS_STATE}"; then
  fail "GAP-2b: prune guard must NOT emit rm -rf on HARNESS_STATE_DIR itself" \
    "absent" "present"
else
  pass "GAP-2b: prune guard does NOT wipe HARNESS_STATE_DIR itself for task-subdir case"
fi

echo ""

# ---------------------------------------------------------------------------
# GAP-2 RED proof: removing HARNESS_STATE_DIR from guard causes dangerous output
# Simulate guard removal by omitting the HARNESS_STATE_DIR clause.
# The flat-file case should then produce "rm -rf <HARNESS_STATE_DIR>".
# ---------------------------------------------------------------------------
echo "-- GAP-2 RED proof: guard removal → dangerous 'rm -rf HARNESS_STATE_DIR' --"

MUTANT_OUT=$(
  STATE_DIR="$FAKE_REPO_STATE"
  HARNESS_STATE_DIR="$FAKE_HARNESS_STATE"
  STALE_PATHS=("$FLAT_FILE")
  # Guard WITHOUT the HARNESS_STATE_DIR clause (simulates the pre-fix / reverted form)
  for f in "${STALE_PATHS[@]}"; do
    dir="$(dirname "$f")"
    if [[ "$dir" == "$STATE_DIR" ]]; then
      echo "rm $f"
    else
      echo "rm -rf $dir"
    fi
  done
)

if echo "$MUTANT_OUT" | grep -qF "rm -rf ${FAKE_HARNESS_STATE}"; then
  pass "GAP-2 RED proof: guard removal causes dangerous 'rm -rf ${FAKE_HARNESS_STATE}' (mutation detected)"
else
  fail "GAP-2 RED proof: expected dangerous rm -rf when guard removed" \
    "rm -rf ${FAKE_HARNESS_STATE} in output" \
    "$(echo "$MUTANT_OUT" | head -3 || echo '(empty)')"
fi

# Confirm the script's prune guard specifically contains HARNESS_STATE_DIR in the rm conditional.
# This catches guard removal from the script (the inline tests above test the logic itself;
# this test catches drift between the script and the tested logic).
echo ""
echo "-- GAP-2 source check: detect-stale prune guard line contains HARNESS_STATE_DIR in rm check --"
if grep -qE '"\$dir"[[:space:]]*==[[:space:]]*"\$HARNESS_STATE_DIR"' "$DETECT_STALE" 2>/dev/null; then
  pass "GAP-2 source: detect-stale prune guard rm-check contains HARNESS_STATE_DIR clause"
else
  fail "GAP-2 source: HARNESS_STATE_DIR in prune guard rm-check" \
    "present" "absent — guard removed from script (see scripts/detect-stale-pipeline-state.sh prune section)"
fi

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

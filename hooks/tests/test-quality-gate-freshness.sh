#!/usr/bin/env bash
# Test harness for _qg_check_freshness worktree-path extraction in
# hooks/_lib/quality-gate-checks.sh.
#
# Covers:
#   (a) multiline command with "cd <worktree> && ..." on a LATER line
#       resolves the worktree path correctly
#   (b) multiline command with NO worktree path falls back gracefully
#       (no false-positive crash; reports "no verification-evidence")
#   (c) single-line command behaviour unchanged (regression guard)
#
# Run from any directory:
#   bash hooks/tests/test-quality-gate-freshness.sh
# Exit 0 = all pass, 1 = any failure.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKS_LIB="$HOOKS_DIR/_lib/quality-gate-checks.sh"

PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

run_exit_test() {
  local name="$1" expected="$2" actual="$3"
  [[ "$actual" -eq "$expected" ]] && pass "$name" || fail "$name" "$expected" "$actual"
}

echo "=== quality-gate freshness extraction Test Harness ==="
echo ""

# ---------------------------------------------------------------------------
# Fixture: a real git worktree we can point at.
# We use git init + an empty commit so git rev-parse HEAD works correctly.
# ---------------------------------------------------------------------------
WT_DIR=$(mktemp -d)
EVT_DIR=$(mktemp -d)
trap 'rm -rf "$WT_DIR" "$EVT_DIR"' EXIT

# Real git repo so git -C "$WT_DIR" rev-parse HEAD returns a valid SHA
git -C "$WT_DIR" init --quiet
git -C "$WT_DIR" -c user.email="test@test" -c user.name="Test" \
    commit --allow-empty -m "fixture" --quiet
REAL_SHA=$(git -C "$WT_DIR" rev-parse HEAD)

# Seed a valid verification-evidence.json matching the real HEAD SHA
mkdir -p "$WT_DIR/pipeline-state/test-task"
printf '{"task_id":"test-task","verdict":"VERIFIED_OK","git_head":"%s","timestamp":"2026-01-01T00:00:00Z","branch":"main"}\n' \
  "$REAL_SHA" > "$WT_DIR/pipeline-state/test-task/verification-evidence.json"

# We also need a harness-paths stub to keep the source chain happy.
# quality-gate-checks.sh does NOT source harness-paths itself, so we only need
# to stub the functions it calls that live outside the file:
#   _qg_resolve_intake_path, _qg_extract_intake_tier — both defined in the same file, no extra deps.
# jq must be available (it is on CI and dev macs).

# ---------------------------------------------------------------------------
# Helper: run _qg_check_freshness in a sub-shell with controlled env.
# Returns the exit code of the function.
# ---------------------------------------------------------------------------
run_freshness() {
  local cmd="$1"
  (
    export CLAUDE_DISABLE_FRESHNESS_QG=0
    export CLAUDE_PIPELINE_TASK_ID="test-task"
    # Point intake to a nonexistent file so tier check is skipped (returns "")
    # shellcheck source=../_lib/quality-gate-checks.sh
    source "$CHECKS_LIB"
    _qg_check_freshness "$cmd" 2>/dev/null
  )
}

# ---------------------------------------------------------------------------
# (c) Single-line — cd is on the FIRST and only line.
# Expected: PASS (exit 0) — regression guard.
# ---------------------------------------------------------------------------
echo "-- (c) single-line command (regression guard) --"

SINGLE_LINE_CMD="cd ${WT_DIR} && some command that does stuff"
run_freshness "$SINGLE_LINE_CMD"
run_exit_test "single-line: cd <worktree> && ... → PASS" 0 $?

# Single-line with NO worktree (cd missing entirely) → evidence lookup falls back
# to cwd which has no pipeline-state → should fail (exit 1)
run_freshness "some command with no cd prefix"
run_exit_test "single-line: no cd prefix → fail (no evidence)" 1 $?

echo ""

# ---------------------------------------------------------------------------
# (a) Multiline — cd <worktree> appears on line 2 (not line 1).
# Before the fix, sed output the full multiline text as wt, which failed -d.
# After the fix, wt is correctly extracted and the evidence is found.
# Expected: PASS (exit 0).
# ---------------------------------------------------------------------------
echo "-- (a) multiline command: cd on later line --"

MULTI_LINE_A="export SOME_VAR=value
cd ${WT_DIR} && run the actual command here"
run_freshness "$MULTI_LINE_A"
run_exit_test "multiline: cd on line 2 → PASS" 0 $?

MULTI_LINE_B="set -e
set -u
cd ${WT_DIR} && do_work && wrap_up"
run_freshness "$MULTI_LINE_B"
run_exit_test "multiline: cd on line 3 → PASS" 0 $?

# Quoted worktree path in multiline command
MULTI_LINE_QUOTED="export FOO=bar
cd \"${WT_DIR}\" && do_work"
run_freshness "$MULTI_LINE_QUOTED"
run_exit_test "multiline: quoted cd on line 2 → PASS" 0 $?

echo ""

# ---------------------------------------------------------------------------
# (b) Multiline — no cd worktree path anywhere → graceful fallback.
# Should return exit 1 (no evidence at cwd), not crash.
# Expected: exit 1 (no verification-evidence).
# ---------------------------------------------------------------------------
echo "-- (b) multiline command: no worktree → graceful fallback --"

MULTI_NO_WT="export A=1
export B=2
run_something_without_cd"
run_freshness "$MULTI_NO_WT"
run_exit_test "multiline: no cd → exit 1 (no evidence, not crash)" 1 $?

# Multiline where cd targets a non-existent path (directory check fails → fallback)
MULTI_BAD_WT="cd /nonexistent/path/abcde12345 && do work"
run_freshness "$MULTI_BAD_WT"
run_exit_test "single-line: cd non-existent path → exit 1 (fallback to cwd, no evidence)" 1 $?

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

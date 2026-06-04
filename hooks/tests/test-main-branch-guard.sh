#!/usr/bin/env bash
# Tests for main-branch-guard self-denial fix (slice-2).
# Regression tests: cd <worktree> && gh pr create must exit 0 from worktree CWD.
# Fix: main-branch-detect.sh:174 REPO_ROOT derived from porcelain head -1, not git rev-parse.
#
# Run from repo root: bash hooks/tests/test-main-branch-guard.sh
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

echo "=== main-branch-guard (self-denial) Test Harness ==="
echo ""

# -- Syntax check -------------------------------------------------------------
echo "-- syntax --"
bash -n "$HOOKS_DIR/main-branch-guard.sh" > /dev/null 2>&1
run_test "syntax valid" 0 $?
bash -n "$HOOKS_DIR/_lib/main-branch-detect.sh" > /dev/null 2>&1
run_test "main-branch-detect.sh syntax valid" 0 $?

# Build hermetic scratch repo + worktree
MBG_TMP=$(mktemp -d)
MBG_MAIN="$MBG_TMP/main-repo"
git init -q "$MBG_MAIN" 2>/dev/null
(cd "$MBG_MAIN" && git commit -q --allow-empty -m init 2>/dev/null)
MBG_WT="$MBG_MAIN/.claude/worktrees/agent-mbg-testid"
mkdir -p "$MBG_MAIN/.claude/worktrees"
(cd "$MBG_MAIN" && git worktree add -q "$MBG_WT" -b worktree-agent-mbg-testid 2>/dev/null)

run_mbg() {
  # $1 = command string, $2 = CWD
  local cmd="$1"
  local cwd="$2"
  (
    cd "$cwd" || return 1
    jq -nc --arg c "$cmd" \
      '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/main-branch-guard.sh" > /dev/null 2>&1
  )
}

# -- Self-denial regression tests ---------------------------------------------
echo "-- self-denial: cd <worktree> && gh pr create --"

# AC-2.1: Hook CWD = registered worktree; cd <worktree> && gh pr create -> exits 0
# Before fix: git rev-parse --show-toplevel from worktree CWD returns worktree root,
# so REPO_ROOT equals worktree and the delegation target matches REPO_ROOT -> blocked.
# After fix: REPO_ROOT from porcelain head -1 is correct main tree -> worktree != REPO_ROOT -> allowed.
run_mbg "cd ${MBG_WT} && gh pr create --base main" "$MBG_WT"
run_test "self-denial: cd <registered-worktree> && gh pr create -> exits 0 from worktree CWD" 0 $?

# AC-2.1: Hook CWD = worktree; command cd REPO_ROOT && git checkout main -> must still be blocked
# The guard must block mutations targeting REPO_ROOT even from a worktree CWD.
run_mbg "cd ${MBG_MAIN} && git checkout main" "$MBG_WT"
run_test "self-denial: cd REPO_ROOT from worktree CWD -> still blocked (exit 2)" 2 $?

# -- Non-denial: hook CWD = REPO_ROOT; cd worktree && gh pr create -> exits 0
echo "-- non-denial: cd <worktree> from root CWD --"
run_mbg "cd ${MBG_WT} && gh pr create --base main" "$MBG_MAIN"
run_test "non-denial: cd <worktree> from root CWD -> exits 0" 0 $?

# -- Baseline: git checkout main at root is still blocked
echo "-- baseline: root-blocking still enforced --"
run_mbg "git checkout main" "$MBG_MAIN"
run_test "baseline: git checkout main at root -> blocked (exit 2)" 2 $?

# Cleanup
(cd "$MBG_MAIN" && git worktree remove --force "$MBG_WT" 2>/dev/null)
rm -rf "$MBG_TMP"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0

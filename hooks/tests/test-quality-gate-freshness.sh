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
#   (new) AC-1a: repro Story A regression guard (cd on line 1, multiline body)
#   (new) AC-1b: root-evidence fallback via --git-common-dir
#   (new) AC-1c-i: substitution rejection (git_head = registered worktree HEAD)
#   (new) AC-1c-ii: unknown SHA rejection (git_head matches no worktree)
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
trap 'rm -rf "$WT_DIR"' EXIT

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

# run_freshness_stderr: captures stderr (for message assertions), suppresses stdout.
run_freshness_stderr() {
  local cmd="$1"
  (
    export CLAUDE_DISABLE_FRESHNESS_QG=0
    export CLAUDE_PIPELINE_TASK_ID="test-task"
    source "$CHECKS_LIB"
    _qg_check_freshness "$cmd" 2>&1 >/dev/null
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
# Hermetic fixture for AC-1a, AC-1b, AC-1c-i, AC-1c-ii:
# genuine git worktree relationship (git init + git worktree add).
# ROOT_DIR = main checkout; WT_DIR2 = registered worktree.
# After a distinguishing commit on WT_DIR2: ROOT_HEAD != WT_HEAD2.
# ROOT_HEAD IS a registered worktree HEAD (main checkout).
# ---------------------------------------------------------------------------
FIXTURE_TMP=$(mktemp -d)
ROOT_DIR="$FIXTURE_TMP/main-repo"
WT_DIR2="$ROOT_DIR/.claude/worktrees/agent-testid"
trap 'rm -rf "$WT_DIR" "$FIXTURE_TMP"' EXIT

git init -q "$ROOT_DIR"
git -C "$ROOT_DIR" -c user.email="t@t" -c user.name="T" commit --allow-empty -m "init" -q
mkdir -p "$ROOT_DIR/.claude/worktrees"
git -C "$ROOT_DIR" worktree add -q "$WT_DIR2" -b worktree-test-branch 2>/dev/null
ROOT_HEAD=$(git -C "$ROOT_DIR" rev-parse HEAD)
# Make a distinguishing commit on WT_DIR2 branch so ROOT_HEAD != WT_HEAD2
git -C "$WT_DIR2" -c user.email="t@t" -c user.name="T" commit --allow-empty -m "wt-commit" -q
WT_HEAD2=$(git -C "$WT_DIR2" rev-parse HEAD)
# Sanity: they must differ
[[ "$ROOT_HEAD" != "$WT_HEAD2" ]] || { echo "FIXTURE ERROR: ROOT_HEAD == WT_HEAD2 after distinguishing commit"; exit 2; }

# ---------------------------------------------------------------------------
# AC-1a: Story A regression guard.
# cd <worktree> on line 1 with multiline body (gh pr create --body "line1\nline2").
# Evidence at WT_DIR2/pipeline-state/test-task/ with git_head=WT_HEAD2.
# Expected: PASS (exit 0).
# ---------------------------------------------------------------------------
echo "-- (AC-1a) repro Story A: cd on line 1 with multiline body --"

mkdir -p "$WT_DIR2/pipeline-state/test-task"
printf '{"task_id":"test-task","verdict":"VERIFIED_OK","git_head":"%s","timestamp":"2026-01-01T00:00:00Z","branch":"main"}\n' \
  "$WT_HEAD2" > "$WT_DIR2/pipeline-state/test-task/verification-evidence.json"

REPRO_A_CMD="cd ${WT_DIR2} && gh pr create --title \"Fix\" --body \"line1
line2
line3\""
run_freshness "$REPRO_A_CMD"
run_exit_test "repro-story-a: cd on line 1 with multiline body → PASS" 0 $?

echo ""

# ---------------------------------------------------------------------------
# AC-1b: Root-evidence fallback.
# Evidence ONLY at ROOT_DIR/pipeline-state/test-task/; none in WT_DIR2.
# git_head=WT_HEAD2 (matches worktree HEAD).
# Expected: PASS (exit 0).
# ---------------------------------------------------------------------------
echo "-- (AC-1b) root-evidence fallback: genuine worktree, evidence only at root --"

# Remove evidence from WT_DIR2 (if any) and place it only at ROOT_DIR
rm -rf "$WT_DIR2/pipeline-state"
mkdir -p "$ROOT_DIR/pipeline-state/test-task"
printf '{"task_id":"test-task","verdict":"VERIFIED_OK","git_head":"%s","timestamp":"2026-01-01T00:00:00Z","branch":"main"}\n' \
  "$WT_HEAD2" > "$ROOT_DIR/pipeline-state/test-task/verification-evidence.json"

ROOT_FALLBACK_CMD="cd ${WT_DIR2} && gh pr create --title \"Fix\""
run_freshness "$ROOT_FALLBACK_CMD"
run_exit_test "root-evidence-fallback: genuine worktree, evidence only at root, git_head=wt_head → PASS" 0 $?

echo ""

# ---------------------------------------------------------------------------
# AC-1c-i: Substitution rejection.
# Evidence at ROOT_DIR; git_head=ROOT_HEAD (ROOT checkout IS a registered worktree).
# Expected: exit 1 + stderr contains "possible evidence substitution".
# ---------------------------------------------------------------------------
echo "-- (AC-1c-i) substitution rejection: git_head=root-checkout-HEAD --"

printf '{"task_id":"test-task","verdict":"VERIFIED_OK","git_head":"%s","timestamp":"2026-01-01T00:00:00Z","branch":"main"}\n' \
  "$ROOT_HEAD" > "$ROOT_DIR/pipeline-state/test-task/verification-evidence.json"

SUBST_CMD="cd ${WT_DIR2} && gh pr create --title \"Fix\""
SUBST_STDERR=$(run_freshness_stderr "$SUBST_CMD")
SUBST_EXIT=$?
run_exit_test "substitution-rejection: git_head=root-checkout-HEAD (registered worktree) → FAIL" 1 "$SUBST_EXIT"
if echo "$SUBST_STDERR" | grep -q "possible evidence substitution"; then
  pass "substitution-rejection: stderr contains 'possible evidence substitution'"
else
  fail "substitution-rejection: stderr message" "possible evidence substitution" "$SUBST_STDERR"
fi

echo ""

# ---------------------------------------------------------------------------
# AC-1c-ii: Unknown SHA rejection.
# Evidence git_head=fabricated SHA matching no registered worktree.
# Expected: exit 1 + stderr contains "matches no registered worktree HEAD".
# ---------------------------------------------------------------------------
echo "-- (AC-1c-ii) unknown-SHA rejection: git_head=fabricated-SHA --"

FABRICATED_SHA="deadbeef0000000000000000000000000000000000"
printf '{"task_id":"test-task","verdict":"VERIFIED_OK","git_head":"%s","timestamp":"2026-01-01T00:00:00Z","branch":"main"}\n' \
  "$FABRICATED_SHA" > "$ROOT_DIR/pipeline-state/test-task/verification-evidence.json"

UNKNOWN_CMD="cd ${WT_DIR2} && gh pr create --title \"Fix\""
UNKNOWN_STDERR=$(run_freshness_stderr "$UNKNOWN_CMD")
UNKNOWN_EXIT=$?
run_exit_test "unknown-sha-rejection: git_head=fabricated-SHA matching no worktree → FAIL" 1 "$UNKNOWN_EXIT"
if echo "$UNKNOWN_STDERR" | grep -q "matches no registered worktree HEAD"; then
  pass "unknown-sha-rejection: stderr contains 'matches no registered worktree HEAD'"
else
  fail "unknown-sha-rejection: stderr message" "matches no registered worktree HEAD" "$UNKNOWN_STDERR"
fi

echo ""

# ---------------------------------------------------------------------------
# AC-1c-iii: Worktree enumeration failure.
# Simulate `git worktree list` failure by pointing GIT_DIR at a nonexistent
# directory inside the sub-shell that runs _qg_check_freshness. The awk
# pipeline produces no output, so matched_wt is empty and wt_list_output is
# also empty — this triggers the new "could not enumerate worktrees" branch.
# Evidence git_head=WT_HEAD2 (would match wt_head, but can't enumerate).
# Expected: exit 1 + stderr contains "could not enumerate worktrees".
# ---------------------------------------------------------------------------
echo "-- (AC-1c-iii) worktree enumeration failure --"

# Restore evidence with WT_HEAD2 so git_head != wt_head triggers the mismatch
# path inside _qg_check_freshness (needed to reach the worktree-list branch).
printf '{"task_id":"test-task","verdict":"VERIFIED_OK","git_head":"%s","timestamp":"2026-01-01T00:00:00Z","branch":"main"}\n' \
  "$ROOT_HEAD" > "$ROOT_DIR/pipeline-state/test-task/verification-evidence.json"

ENUM_FAIL_STDERR=$(
  (
    export CLAUDE_DISABLE_FRESHNESS_QG=0
    export CLAUDE_PIPELINE_TASK_ID="test-task"
    # Override git to always fail for worktree list by wrapping via PATH
    FAKE_GIT_DIR=$(mktemp -d)
    cat > "$FAKE_GIT_DIR/git" <<'GITEOF'
#!/usr/bin/env bash
# Intercept "worktree list --porcelain" only; delegate everything else.
if [[ "$*" == *"worktree list"* ]]; then
  exit 1
fi
exec /usr/bin/git "$@"
GITEOF
    chmod +x "$FAKE_GIT_DIR/git"
    source "$CHECKS_LIB"
    PATH="$FAKE_GIT_DIR:$PATH" _qg_check_freshness "cd ${WT_DIR2} && some cmd" 2>&1 >/dev/null
    RET=$?
    rm -rf "$FAKE_GIT_DIR"
    exit $RET
  )
)
ENUM_FAIL_EXIT=$?
run_exit_test "enumeration-failure: git worktree list fails → FAIL (exit 1)" 1 "$ENUM_FAIL_EXIT"
if echo "$ENUM_FAIL_STDERR" | grep -q "could not enumerate worktrees"; then
  pass "enumeration-failure: stderr contains 'could not enumerate worktrees'"
else
  fail "enumeration-failure: stderr message" "could not enumerate worktrees" "$ENUM_FAIL_STDERR"
fi

echo ""

# ---------------------------------------------------------------------------
# Probe-5 gap-fill: worktree path with spaces — awk substr($0,10) vs $2.
# Create a genuine git worktree whose path contains a space; verify that
# substitution-rejection still emits "possible evidence substitution" (not a
# garbled or empty matched_wt path). This kills the surviving awk $2 mutant.
# ---------------------------------------------------------------------------
echo "-- (space-in-path) awk substr vs \$2: worktree path containing a space --"

SPACE_FIXTURE_TMP=$(mktemp -d)
SPACE_ROOT_DIR="$SPACE_FIXTURE_TMP/main repo"   # space in name
SPACE_WT_DIR="$SPACE_ROOT_DIR/.claude/worktrees/agent with space"
trap 'rm -rf "$WT_DIR" "$FIXTURE_TMP" "$SPACE_FIXTURE_TMP"' EXIT

mkdir -p "$SPACE_ROOT_DIR"
git init -q "$SPACE_ROOT_DIR"
git -C "$SPACE_ROOT_DIR" -c user.email="t@t" -c user.name="T" commit --allow-empty -m "init" -q
mkdir -p "$SPACE_ROOT_DIR/.claude/worktrees"
git -C "$SPACE_ROOT_DIR" worktree add -q "$SPACE_WT_DIR" -b space-test-branch 2>/dev/null
SPACE_ROOT_HEAD=$(git -C "$SPACE_ROOT_DIR" rev-parse HEAD)
git -C "$SPACE_WT_DIR" -c user.email="t@t" -c user.name="T" commit --allow-empty -m "wt-commit" -q
SPACE_WT_HEAD=$(git -C "$SPACE_WT_DIR" rev-parse HEAD)
[[ "$SPACE_ROOT_HEAD" != "$SPACE_WT_HEAD" ]] || { echo "FIXTURE ERROR: space path SHAs not distinct"; FAIL=$((FAIL+1)); }

# Place evidence at root with ROOT_HEAD (triggers substitution-rejection path)
mkdir -p "$SPACE_ROOT_DIR/pipeline-state/test-task"
printf '{"task_id":"test-task","verdict":"VERIFIED_OK","git_head":"%s","timestamp":"2026-01-01T00:00:00Z","branch":"main"}\n' \
  "$SPACE_ROOT_HEAD" > "$SPACE_ROOT_DIR/pipeline-state/test-task/verification-evidence.json"

SPACE_SUBST_CMD="cd \"${SPACE_WT_DIR}\" && gh pr create --title \"Fix\""
SPACE_SUBST_STDERR=$(
  (
    export CLAUDE_DISABLE_FRESHNESS_QG=0
    export CLAUDE_PIPELINE_TASK_ID="test-task"
    source "$CHECKS_LIB"
    _qg_check_freshness "$SPACE_SUBST_CMD" 2>&1 >/dev/null
  )
)
SPACE_SUBST_EXIT=$?
run_exit_test "space-in-path: substitution-rejection → exit 1" 1 "$SPACE_SUBST_EXIT"
if echo "$SPACE_SUBST_STDERR" | grep -q "possible evidence substitution"; then
  pass "space-in-path: stderr contains 'possible evidence substitution' (awk substr preserves spaces)"
else
  fail "space-in-path: stderr message" "possible evidence substitution" "$SPACE_SUBST_STDERR"
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

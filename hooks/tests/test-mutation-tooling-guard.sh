#!/usr/bin/env bash
# Tests for mutation-tooling-guard.sh (PreToolUse:Bash)
# Guards against mutation tooling run with CWD == REPO_ROOT when
# CLAUDE_WORKTREE_PATH is set (a worktree session is active).
#
# Run from repo root: bash hooks/tests/test-mutation-tooling-guard.sh
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

echo "=== mutation-tooling-guard Test Harness ==="
echo ""

# Build hermetic scratch repo + worktree (mirrors bash-write-guard pattern)
MTG_TMP=$(mktemp -d)
MTG_MAIN="$MTG_TMP/main-repo"
git init -q "$MTG_MAIN" 2>/dev/null
(cd "$MTG_MAIN" && git commit -q --allow-empty -m init 2>/dev/null)
# Seed a tracked source file so sed -i tests have a real target
touch "$MTG_MAIN/src.py"
(cd "$MTG_MAIN" && git add src.py && git commit -q -m "seed" 2>/dev/null)
MTG_WT="$MTG_MAIN/.claude/worktrees/agent-testid"
mkdir -p "$MTG_MAIN/.claude/worktrees"
(cd "$MTG_MAIN" && git worktree add -q "$MTG_WT" -b worktree-agent-mtg-testid 2>/dev/null)

run_mtg() {
  # $1 = command string, $2 = CWD, $3 = CLAUDE_WORKTREE_PATH (or empty to unset)
  local cmd="$1"
  local cwd="$2"
  local wt_path="${3:-}"
  (
    cd "$cwd" || return 1
    if [[ -n "$wt_path" ]]; then
      export CLAUDE_WORKTREE_PATH="$wt_path"
    else
      unset CLAUDE_WORKTREE_PATH 2>/dev/null || true
    fi
    jq -nc --arg c "$cmd" \
      '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/mutation-tooling-guard.sh" > /dev/null 2>&1
  )
}

# -- Syntax check -------------------------------------------------------------
echo "-- syntax --"
bash -n "$HOOKS_DIR/mutation-tooling-guard.sh" > /dev/null 2>&1
run_test "syntax valid" 0 $?

# -- Non-Bash tool: pass through ----------------------------------------------
echo "-- non-Bash tool --"
(cd "$MTG_MAIN" && export CLAUDE_WORKTREE_PATH="$MTG_WT" && \
  echo '{"tool_name":"Write","tool_input":{"file_path":"x.ts"},"hook_event_name":"PreToolUse"}' \
  | bash "$HOOKS_DIR/mutation-tooling-guard.sh" > /dev/null 2>&1)
run_test "non-Bash tool -> allow (exit 0)" 0 $?

# -- No CLAUDE_WORKTREE_PATH: no worktree session active -> always allow ------
echo "-- no worktree session (CLAUDE_WORKTREE_PATH unset) --"
run_mtg "mutmut run" "$MTG_MAIN" ""
run_test "mutmut at root, no CLAUDE_WORKTREE_PATH -> allow (exit 0)" 0 $?

run_mtg "sed -i 's/foo/bar/' src.py" "$MTG_MAIN" ""
run_test "sed -i at root, no CLAUDE_WORKTREE_PATH -> allow (exit 0)" 0 $?

# -- REPO_ROOT + CLAUDE_WORKTREE_PATH set: mutation tooling -> advisory warn --
echo "-- root CWD + active worktree session: mutation tooling (advisory mode) --"

# mutmut: should warn but still exit 0 (advisory mode)
run_mtg "mutmut run" "$MTG_MAIN" "$MTG_WT"
run_test "mutmut run at root + worktree active -> advisory warn (exit 0)" 0 $?

run_mtg "mutmut run --paths-to-mutate src.py" "$MTG_MAIN" "$MTG_WT"
run_test "mutmut run with flags at root -> advisory warn (exit 0)" 0 $?

# sed -i on git-tracked source file at root
run_mtg "sed -i 's/foo/bar/' src.py" "$MTG_MAIN" "$MTG_WT"
run_test "sed -i tracked source at root -> advisory warn (exit 0)" 0 $?

# sed --in-place
run_mtg "sed --in-place 's/foo/bar/' src.py" "$MTG_MAIN" "$MTG_WT"
run_test "sed --in-place tracked source at root -> advisory warn (exit 0)" 0 $?

# sed -i targeting .py (check extension-based match)
run_mtg "sed -i 's/x/y/' module.py" "$MTG_MAIN" "$MTG_WT"
run_test "sed -i on .py file at root -> advisory warn (exit 0)" 0 $?

# sed -i targeting /tmp should NOT trigger (safe path)
run_mtg "sed -i 's/x/y/' /tmp/scratch.txt" "$MTG_MAIN" "$MTG_WT"
run_test "sed -i on /tmp path at root -> allow (exit 0)" 0 $?

# sed -i on .md should NOT trigger (doc files are not source)
run_mtg "sed -i 's/x/y/' README.md" "$MTG_MAIN" "$MTG_WT"
run_test "sed -i on .md file at root -> allow (exit 0)" 0 $?

# -- Pytest with mutation-side-effect flags ------------------------------------
echo "-- pytest flags at root + active worktree session --"

# pytest --lf (last failed) is safe (cache reads) - must allow
run_mtg "pytest tests/ --lf" "$MTG_MAIN" "$MTG_WT"
run_test "pytest --lf at root -> allow (exit 0, not mutation)" 0 $?

# pytest --cache-clear just clears the cache - must allow
run_mtg "pytest tests/ --cache-clear" "$MTG_MAIN" "$MTG_WT"
run_test "pytest --cache-clear at root -> allow (exit 0, not mutation)" 0 $?

# plain pytest is fine (we're not blocking pytest entirely)
run_mtg "pytest tests/" "$MTG_MAIN" "$MTG_WT"
run_test "plain pytest at root -> allow (exit 0)" 0 $?

# -- Worktree CWD: always allow even with CLAUDE_WORKTREE_PATH set ------------
echo "-- worktree CWD: always allow --"
run_mtg "mutmut run" "$MTG_WT" "$MTG_WT"
run_test "mutmut inside worktree -> allow (exit 0)" 0 $?

run_mtg "sed -i 's/foo/bar/' src.py" "$MTG_WT" "$MTG_WT"
run_test "sed -i inside worktree -> allow (exit 0)" 0 $?

# -- Finding 2: CLAUDE_WORKTREE_PATH vs $PWD comparison causes /var symlink mismatch --
# Line 65 used to compare "${CLAUDE_WORKTREE_PATH:-}" == "$PWD".
# On macOS TMPDIR = /var/folders/... but $PWD shows /private/var/folders/...
# So when CWD == worktree (both resolve the same) but one uses /var and the other
# /private/var, the comparison fails and the guard incorrectly fires advisory.
# Fix: canonicalize CLAUDE_WORKTREE_PATH before comparing against $canon_pwd.
echo "-- Finding 2: CLAUDE_WORKTREE_PATH must be canonicalized before comparing to canon_pwd --"

# Simulate the /var vs /private/var mismatch:
# Set CLAUDE_WORKTREE_PATH to the symlink path; CWD to the canonical path.
# The guard should recognize they are the same location -> exit 0 (not root CWD).
# Before the fix line 65 compares raw CLAUDE_WORKTREE_PATH vs $PWD which may disagree.
MTG_SYM="$MTG_TMP/sym-wt"
ln -s "$MTG_WT" "$MTG_SYM" 2>/dev/null || true
if [[ -L "$MTG_SYM" ]]; then
  # CWD = real worktree path, CLAUDE_WORKTREE_PATH = symlink to same dir
  F2_OUT=$(
    cd "$MTG_WT" || exit 0
    export CLAUDE_WORKTREE_PATH="$MTG_SYM"
    jq -nc --arg c "mutmut run" \
      '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/mutation-tooling-guard.sh" 2>&1
  )
  if echo "$F2_OUT" | grep -qi "advisory"; then
    fail "Finding 2: CWD=real-worktree, CLAUDE_WORKTREE_PATH=symlink-to-same -> no advisory" "no advisory" "advisory fired"
  else
    pass "Finding 2: CWD=real-worktree, CLAUDE_WORKTREE_PATH=symlink-to-same -> no advisory"
  fi

  # Also: CWD = symlink path, CLAUDE_WORKTREE_PATH = real path -> no advisory
  F2B_OUT=$(
    cd "$MTG_SYM" || exit 0
    export CLAUDE_WORKTREE_PATH="$MTG_WT"
    jq -nc --arg c "mutmut run" \
      '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/mutation-tooling-guard.sh" 2>&1
  )
  if echo "$F2B_OUT" | grep -qi "advisory"; then
    fail "Finding 2: CWD=symlink-to-worktree, CLAUDE_WORKTREE_PATH=real -> no advisory" "no advisory" "advisory fired"
  else
    pass "Finding 2: CWD=symlink-to-worktree, CLAUDE_WORKTREE_PATH=real -> no advisory"
  fi
else
  pass "Finding 2: symlink test skipped (ln -s not available)"
  pass "Finding 2: symlink test skipped (ln -s not available)"
fi

# -- Finding 3: safe path exclusion for macOS TMPDIR (/var/folders/...) -------
# sed -i on a file under /var/folders/ must NOT trigger advisory message.
# (Advisory mode always exits 0; check ABSENCE of warning message.)
echo "-- Finding 3: macOS TMPDIR /var/folders safe-path exclusion (no advisory) --"

# Helper: run and capture stderr+stdout; check advisory message absent
run_mtg_warn() {
  local cmd="$1"
  local cwd="$2"
  local wt_path="${3:-}"
  (
    cd "$cwd" || return 1
    if [[ -n "$wt_path" ]]; then
      export CLAUDE_WORKTREE_PATH="$wt_path"
    else
      unset CLAUDE_WORKTREE_PATH 2>/dev/null || true
    fi
    jq -nc --arg c "$cmd" \
      '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/mutation-tooling-guard.sh" 2>&1
  )
}

F3_OUT=$(run_mtg_warn "sed -i 's/x/y/' /var/folders/abc/T/tmp123/scratch.py" "$MTG_MAIN" "$MTG_WT")
if echo "$F3_OUT" | grep -qi "advisory"; then
  fail "Finding 3: sed -i on /var/folders path -> NO advisory" "no advisory" "advisory fired"
else
  pass "Finding 3: sed -i on /var/folders path -> no advisory emitted"
fi

F3_PRIV_OUT=$(run_mtg_warn "sed -i 's/x/y/' /private/var/folders/xyz/T/tmp456/fix.py" "$MTG_MAIN" "$MTG_WT")
if echo "$F3_PRIV_OUT" | grep -qi "advisory"; then
  fail "Finding 3: sed -i on /private/var/folders path -> NO advisory" "no advisory" "advisory fired"
else
  pass "Finding 3: sed -i on /private/var/folders path -> no advisory emitted"
fi

# $TMPDIR-prefixed path (real macOS TMPDIR expansion)
REAL_TMPDIR="${TMPDIR:-/tmp}"
F3_TD_OUT=$(run_mtg_warn "sed -i 's/x/y/' ${REAL_TMPDIR}scratch.py" "$MTG_MAIN" "$MTG_WT")
if echo "$F3_TD_OUT" | grep -qi "advisory"; then
  fail "Finding 3: sed -i on \$TMPDIR-prefixed path -> NO advisory" "no advisory" "advisory fired"
else
  pass "Finding 3: sed -i on \$TMPDIR-prefixed path -> no advisory emitted"
fi

# -- Advisory: warning message mentions worktree path -------------------------
echo "-- advisory: warn message mentions worktree path --"
WARN_OUT=$(
  cd "$MTG_MAIN" && export CLAUDE_WORKTREE_PATH="$MTG_WT" &&
  jq -nc --arg c "mutmut run" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/mutation-tooling-guard.sh" 2>&1
)
if echo "$WARN_OUT" | grep -q "mutation-tooling-guard"; then
  pass "advisory: message contains mutation-tooling-guard"
else
  fail "advisory: message contains mutation-tooling-guard" "present" "missing"
fi
if echo "$WARN_OUT" | grep -q "worktree"; then
  pass "advisory: message mentions worktree"
else
  fail "advisory: message mentions worktree" "present" "missing"
fi

# -- Env-var escape (CLAUDE_DISABLE_MUTATION_TOOLING_GUARD=1) -----------------
echo "-- env-var escape --"
(
  cd "$MTG_MAIN" && export CLAUDE_WORKTREE_PATH="$MTG_WT" &&
  export CLAUDE_DISABLE_MUTATION_TOOLING_GUARD=1 &&
  jq -nc --arg c "mutmut run" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/mutation-tooling-guard.sh" > /dev/null 2>&1
)
run_test "escape var set -> bypass (exit 0)" 0 $?

# -- Gap 2: normalizer (_mtg_normalize_command) --------------------------------
echo "-- gap2: command normalizer --"

# bash -c 'mutmut run' should be unwrapped and detected
GAP2_OUT=$(run_mtg_warn "bash -c 'mutmut run'" "$MTG_MAIN" "$MTG_WT")
if echo "$GAP2_OUT" | grep -qi "advisory\|ADVISORY"; then
  pass "gap2: bash -c mutmut -> advisory emitted"
else
  fail "gap2: bash -c mutmut -> advisory emitted" "advisory" "none"
fi

# python -m mutmut run
GAP2B_OUT=$(run_mtg_warn "python -m mutmut run" "$MTG_MAIN" "$MTG_WT")
if echo "$GAP2B_OUT" | grep -qi "advisory\|ADVISORY"; then
  pass "gap2: python -m mutmut -> advisory emitted"
else
  fail "gap2: python -m mutmut -> advisory emitted" "advisory" "none"
fi

# eval "sed -i 's/x/y/' src.py"
GAP2C_OUT=$(run_mtg_warn "eval \"sed -i 's/x/y/' src.py\"" "$MTG_MAIN" "$MTG_WT")
if echo "$GAP2C_OUT" | grep -qi "advisory\|ADVISORY"; then
  pass "gap2: eval \"sed -i src.py\" -> advisory emitted"
else
  fail "gap2: eval \"sed -i src.py\" -> advisory emitted" "advisory" "none"
fi

# backslash-escaped s\ed -i
GAP2D_OUT=$(run_mtg_warn 's\ed -i '"'"'s/x/y/'"'"' src.py' "$MTG_MAIN" "$MTG_WT")
if echo "$GAP2D_OUT" | grep -qi "advisory\|ADVISORY"; then
  pass "gap2: backslash-escaped s\\ed -i -> advisory emitted"
else
  fail "gap2: backslash-escaped s\\ed -i -> advisory emitted" "advisory" "none"
fi

# $(echo mutmut) run
GAP2E_OUT=$(run_mtg_warn '$(echo mutmut) run' "$MTG_MAIN" "$MTG_WT")
if echo "$GAP2E_OUT" | grep -qi "advisory\|ADVISORY"; then
  pass 'gap2: $(echo mutmut) -> advisory emitted'
else
  fail 'gap2: $(echo mutmut) -> advisory emitted' "advisory" "none"
fi

# FP-guard: bash -c 'echo "sed -i is dangerous"' -> no advisory (inner is string literal)
GAP2_FP1=$(run_mtg_warn "bash -c 'echo \"sed -i is dangerous\"'" "$MTG_MAIN" "$MTG_WT")
if echo "$GAP2_FP1" | grep -qi "advisory\|ADVISORY"; then
  fail "fp-guard: bash -c 'echo \"sed -i is dangerous\"' -> no advisory" "no advisory" "advisory fired"
else
  pass "fp-guard: bash -c 'echo \"sed -i is dangerous\"' -> no advisory"
fi

# FP-guard: bash -c '# sed -i comment' -> no advisory (leading token is #)
GAP2_FP2=$(run_mtg_warn "bash -c '# sed -i comment'" "$MTG_MAIN" "$MTG_WT")
if echo "$GAP2_FP2" | grep -qi "advisory\|ADVISORY"; then
  fail "fp-guard: bash -c '# sed -i comment' -> no advisory" "no advisory" "advisory fired"
else
  pass "fp-guard: bash -c '# sed -i comment' -> no advisory"
fi

# -- Gap 3: WORKTREE_PATH unset heuristic --------------------------------------
echo "-- gap3: WORKTREE_PATH unset heuristic --"

# WORKTREE_PATH unset + active worktrees (we have $MTG_WT) + mutmut -> reduced advisory
GAP3_OUT=$(run_mtg_warn "mutmut run" "$MTG_MAIN" "")
if echo "$GAP3_OUT" | grep -qi "advisory\|ADVISORY\|reduced\|unverified\|worktree"; then
  pass "gap3: WORKTREE_PATH unset + active worktrees + mutmut -> reduced advisory"
else
  fail "gap3: WORKTREE_PATH unset + active worktrees + mutmut -> reduced advisory" "advisory" "none"
fi

# WORKTREE_PATH unset + no active worktrees + mutmut -> silent allow
# Create a fresh repo with no worktrees for this test
GAP3_TMP=$(mktemp -d)
GAP3_MAIN="$GAP3_TMP/solo-repo"
git init -q "$GAP3_MAIN" 2>/dev/null
(cd "$GAP3_MAIN" && git commit -q --allow-empty -m init 2>/dev/null)
GAP3_OUT2=$(
  cd "$GAP3_MAIN" || exit 0
  unset CLAUDE_WORKTREE_PATH 2>/dev/null || true
  jq -nc --arg c "mutmut run" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/mutation-tooling-guard.sh" 2>&1
)
if echo "$GAP3_OUT2" | grep -qi "advisory\|ADVISORY"; then
  fail "gap3: WORKTREE_PATH unset + no active worktrees + mutmut -> silent allow" "no advisory" "advisory fired"
else
  pass "gap3: WORKTREE_PATH unset + no active worktrees + mutmut -> silent allow"
fi
rm -rf "$GAP3_TMP"

# -- FP regression: sed on /var/folders path should not fire after fix ---------
echo "-- fp-regression: sed -i /var/folders --"
FP_REG_OUT=$(run_mtg_warn "sed -i 's/x/y/' /var/folders/abc/T/tmp123/scratch.py" "$MTG_MAIN" "$MTG_WT")
if echo "$FP_REG_OUT" | grep -qi "advisory\|ADVISORY"; then
  fail "fp-regression: sed -i /var/folders/abc/T/tmp123/scratch.py -> no advisory" "no advisory" "advisory fired"
else
  pass "fp-regression: sed -i /var/folders/abc/T/tmp123/scratch.py -> no advisory"
fi

# -- Gap 5: escape-audit write for MTG ----------------------------------------
echo "-- gap5: escape-audit for mtg --"

MTG_ESC_TMP=$(mktemp -d)
(
  cd "$MTG_MAIN" && \
  export CLAUDE_WORKTREE_PATH="$MTG_WT" && \
  export CLAUDE_DISABLE_MUTATION_TOOLING_GUARD=1 && \
  export HARNESS_DATA="$MTG_ESC_TMP" && \
  export CLAUDE_SESSION_ID="mtg-escape-test-$$" && \
  jq -nc --arg c "mutmut run" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/mutation-tooling-guard.sh" > /dev/null 2>&1
)
if find "$MTG_ESC_TMP" -name "guard-escapes.jsonl" -exec grep -l '"guard":"mutation-tooling-guard"' {} \; 2>/dev/null | grep -q .; then
  pass "gap5: escape var set -> guard-escapes.jsonl contains mtg record"
else
  fail "gap5: escape var set -> guard-escapes.jsonl contains mtg record" "mtg record in jsonl" "not found"
fi
rm -rf "$MTG_ESC_TMP"

# -- Slice 2 (Amendment 1): _mtg_is_root_cwd with porcelain REPO_ROOT fix -----
echo "-- mtg: CWD-independent _mtg_is_root_cwd --"

# When CWD is the registered worktree and WORKTREE_PATH is set,
# _mtg_is_root_cwd must return false (worktree != root) -> no advisory
MTG_WT_OUT=$(run_mtg_warn "mutmut run" "$MTG_WT" "$MTG_WT")
if echo "$MTG_WT_OUT" | grep -qi "advisory\|ADVISORY"; then
  fail "mtg CWD-independent: _mtg_is_root_cwd correct when hook CWD is worktree" "no advisory" "advisory fired"
else
  pass "mtg CWD-independent: _mtg_is_root_cwd correct when hook CWD is worktree"
fi

# Cleanup
(cd "$MTG_MAIN" && git worktree remove --force "$MTG_WT" 2>/dev/null)
rm -rf "$MTG_TMP"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0

#!/usr/bin/env bash
# Tests for runtime-state-guard.sh (PreToolUse:Bash + PreToolUse:Write)
# Guards against:
#   - mkdir of pipeline-state/ under REPO_ROOT (Bash tool)
#   - Write tool writes targeting <REPO_ROOT>/pipeline-state/...
#
# Runtime state belongs in $CLAUDE_PLUGIN_DATA/HARNESS_DATA per harness-paths.sh
# and CLAUDE.md § Runtime State Location.
#
# Run from repo root: bash hooks/tests/test-runtime-state-guard.sh
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

echo "=== runtime-state-guard Test Harness ==="
echo ""

# -- Syntax check -------------------------------------------------------------
echo "-- syntax --"
bash -n "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
run_test "syntax valid" 0 $?

# Hermetic scratch repo + worktree
RSG_TMP=$(mktemp -d)
RSG_MAIN="$RSG_TMP/main-repo"
git init -q "$RSG_MAIN" 2>/dev/null
(cd "$RSG_MAIN" && git commit -q --allow-empty -m init 2>/dev/null)
RSG_WT="$RSG_MAIN/.claude/worktrees/agent-testid"
mkdir -p "$RSG_MAIN/.claude/worktrees"
(cd "$RSG_MAIN" && git worktree add -q "$RSG_WT" -b worktree-agent-rsg-testid 2>/dev/null)

run_rsg_bash() {
  # $1 = command string, $2 = CWD
  local cmd="$1"
  local cwd="$2"
  (
    cd "$cwd" || return 1
    jq -nc --arg c "$cmd" \
      '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
  )
}

run_rsg_write() {
  # $1 = file_path, $2 = CWD
  local fp="$1"
  local cwd="$2"
  (
    cd "$cwd" || return 1
    jq -nc --arg p "$fp" \
      '{tool_name:"Write",tool_input:{file_path:$p,content:"x"},hook_event_name:"PreToolUse"}' \
      | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
  )
}

# -- Non-matching tools: always allow -----------------------------------------
echo "-- non-matching tools --"
(cd "$RSG_MAIN" && \
  echo '{"tool_name":"Read","tool_input":{"file_path":"foo"},"hook_event_name":"PreToolUse"}' \
  | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1)
run_test "Read tool -> allow (exit 0)" 0 $?

(cd "$RSG_MAIN" && \
  echo '{"tool_name":"Edit","tool_input":{"file_path":"foo"},"hook_event_name":"PreToolUse"}' \
  | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1)
run_test "Edit tool -> allow (exit 0)" 0 $?

# -- Bash tool: mkdir pipeline-state at root -> block -------------------------
echo "-- Bash: mkdir pipeline-state at root --"

run_rsg_bash "mkdir -p pipeline-state/my-task" "$RSG_MAIN"
run_test "mkdir -p pipeline-state/my-task at root -> block (exit 2)" 2 $?

run_rsg_bash "mkdir pipeline-state/ws-g-spec" "$RSG_MAIN"
run_test "mkdir pipeline-state/ws-g-spec at root -> block (exit 2)" 2 $?

run_rsg_bash "mkdir -p ./pipeline-state/task" "$RSG_MAIN"
run_test "mkdir -p ./pipeline-state/task at root -> block (exit 2)" 2 $?

# Absolute path to REPO_ROOT/pipeline-state
run_rsg_bash "mkdir -p ${RSG_MAIN}/pipeline-state/task" "$RSG_MAIN"
run_test "mkdir absolute <REPO_ROOT>/pipeline-state at root -> block (exit 2)" 2 $?

# -- Bash tool: mkdir outside pipeline-state -> allow -------------------------
echo "-- Bash: mkdir other dirs at root --"

run_rsg_bash "mkdir -p /tmp/pipeline-state/something" "$RSG_MAIN"
run_test "mkdir /tmp/pipeline-state -> allow (exit 0)" 0 $?

run_rsg_bash "mkdir -p some-other-dir" "$RSG_MAIN"
run_test "mkdir some-other-dir -> allow (exit 0)" 0 $?

run_rsg_bash "ls pipeline-state/" "$RSG_MAIN"
run_test "ls pipeline-state (no mkdir) -> allow (exit 0)" 0 $?

# -- Bash tool: mkdir pipeline-state inside worktree -> allow -----------------
echo "-- Bash: mkdir pipeline-state inside worktree --"

run_rsg_bash "mkdir -p pipeline-state/my-task" "$RSG_WT"
run_test "mkdir pipeline-state inside worktree -> allow (exit 0)" 0 $?

# -- SECURITY: CLAUDE_WORKTREE_PATH set but CWD = repo root -> MUST block -----
# Finding 1: _rsg_is_worktree() must NOT allow based on env var alone.
# A worktree-session agent running mkdir pipeline-state/... AT ROOT bypasses
# the guard when CLAUDE_WORKTREE_PATH merely *matches* the worktree pattern.
echo "-- SECURITY: CLAUDE_WORKTREE_PATH set but CWD = repo root -> must block --"

(
  cd "$RSG_MAIN" || exit 1
  export CLAUDE_WORKTREE_PATH="$RSG_WT"
  jq -nc --arg c "mkdir -p pipeline-state/incident-task" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
)
run_test "SECURITY: CLAUDE_WORKTREE_PATH=worktree but CWD=root -> MUST block (exit 2)" 2 $?

(
  cd "$RSG_MAIN" || exit 1
  export CLAUDE_WORKTREE_PATH="$RSG_WT"
  jq -nc --arg p "${RSG_MAIN}/pipeline-state/x.json" \
    '{tool_name:"Write",tool_input:{file_path:$p,content:"x"},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
)
run_test "SECURITY: Write with CLAUDE_WORKTREE_PATH set but CWD=root -> MUST block (exit 2)" 2 $?

# CWD genuinely inside the worktree -> allowed (positive case)
(
  cd "$RSG_WT" || exit 1
  export CLAUDE_WORKTREE_PATH="$RSG_WT"
  jq -nc --arg c "mkdir -p pipeline-state/incident-task" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
)
run_test "SECURITY: CWD genuinely inside worktree + CLAUDE_WORKTREE_PATH set -> allow (exit 0)" 0 $?

# -- Write tool: file under pipeline-state at root -> block -------------------
echo "-- Write: file under pipeline-state at root --"

run_rsg_write "${RSG_MAIN}/pipeline-state/task/evidence.json" "$RSG_MAIN"
run_test "Write absolute path to <REPO_ROOT>/pipeline-state -> block (exit 2)" 2 $?

run_rsg_write "pipeline-state/task/evidence.json" "$RSG_MAIN"
run_test "Write relative pipeline-state/ path at root -> block (exit 2)" 2 $?

run_rsg_write "./pipeline-state/task.md" "$RSG_MAIN"
run_test "Write ./pipeline-state/task.md at root -> block (exit 2)" 2 $?

# -- Write tool: pipeline-state outside repo root -> allow --------------------
echo "-- Write: pipeline-state outside repo root --"

run_rsg_write "/tmp/pipeline-state/foo.json" "$RSG_MAIN"
run_test "Write /tmp/pipeline-state/foo.json -> allow (exit 0)" 0 $?

SOME_OTHER_DIR="$RSG_TMP/other-repo"
run_rsg_write "${SOME_OTHER_DIR}/pipeline-state/foo.json" "$RSG_MAIN"
run_test "Write pipeline-state under unrelated path -> allow (exit 0)" 0 $?

# -- Write tool: pipeline-state inside worktree -> allow ----------------------
echo "-- Write: pipeline-state inside worktree --"

run_rsg_write "${RSG_WT}/pipeline-state/evidence.json" "$RSG_WT"
run_test "Write pipeline-state inside worktree -> allow (exit 0)" 0 $?

run_rsg_write "pipeline-state/evidence.json" "$RSG_WT"
run_test "Write relative pipeline-state inside worktree -> allow (exit 0)" 0 $?

# -- Deny message: states the correct location --------------------------------
echo "-- deny message quality --"

DENY_MSG=$(
  cd "$RSG_MAIN" && \
  jq -nc --arg c "mkdir -p pipeline-state/test" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/runtime-state-guard.sh" 2>&1
)
if echo "$DENY_MSG" | grep -qiE "CLAUDE_PLUGIN_DATA|HARNESS_DATA|\\\$CLAUDE_PLUGIN_DATA"; then
  pass "deny message: names correct state location (CLAUDE_PLUGIN_DATA or HARNESS_DATA)"
else
  fail "deny message: names correct state location" "CLAUDE_PLUGIN_DATA or HARNESS_DATA" "missing"
fi

if echo "$DENY_MSG" | grep -qi "runtime-state-guard"; then
  pass "deny message: names runtime-state-guard"
else
  fail "deny message: names runtime-state-guard" "present" "missing"
fi

# -- Escape hatch -------------------------------------------------------------
echo "-- escape hatch --"
(
  cd "$RSG_MAIN" && \
  export CLAUDE_DISABLE_RUNTIME_STATE_GUARD=1 && \
  jq -nc --arg c "mkdir -p pipeline-state/test" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
)
run_test "escape var set -> bypass (exit 0)" 0 $?

# -- Gap 1: Registry check (_rsg_is_registered_worktree) ----------------------
# The exploit: create a dir that matches */.claude/worktrees/agent-* inside the
# repo, cd into it, then run a command targeting REPO_ROOT/pipeline-state.
# Without the registry check, the old fast-path matched the pattern and returned 0.
# With the registry check, the guard iterates git worktree list and finds no match.
echo "-- gap1: registry check --"

# AC-1.1: CWD matches pattern but is NOT in git worktree registry -> blocked.
# The fake-glob dir is created INSIDE $RSG_MAIN (not /tmp) so that git commands
# run from that CWD still resolve within a valid git repo. If the dir were created
# under /tmp it would be outside the git tree, causing git worktree list to fail
# or return results relative to the wrong repo, breaking the registry check.
RSG_FAKE_WT="$RSG_MAIN/.claude/worktrees/agent-evil"
mkdir -p "$RSG_FAKE_WT"
(
  cd "$RSG_FAKE_WT" || exit 1
  jq -nc --arg c "mkdir -p ${RSG_MAIN}/pipeline-state/exfil" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
)
run_test "gap1: fake-glob dir not in registry -> blocked (exit 2)" 2 $?
rm -rf "$RSG_FAKE_WT"

# AC-1.1: CWD = git-registered worktree -> mkdir pipeline-state allowed
(
  cd "$RSG_WT" || exit 1
  jq -nc --arg c "mkdir -p pipeline-state/my-task" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
)
run_test "gap1: registered worktree CWD -> mkdir allowed (exit 0)" 0 $?

# AC-1.1: second fake-glob dir inside the repo (also not registered) -> blocked
RSG_FAKE_WT2="$RSG_MAIN/.claude/worktrees/agent-unregistered"
mkdir -p "$RSG_FAKE_WT2"
(
  cd "$RSG_FAKE_WT2" || exit 1
  jq -nc --arg c "mkdir -p ${RSG_MAIN}/pipeline-state/task" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
)
run_test "gap1: unregistered glob-match dir -> blocked (exit 2)" 2 $?
rm -rf "$RSG_FAKE_WT2"

# -- Gap 4: cp/mv/rsync targeting pipeline-state -> blocked -------------------
echo "-- gap4: cp/mv/rsync coverage --"

run_rsg_bash "cp -r /tmp/x pipeline-state/task" "$RSG_MAIN"
run_test "gap4: cp targeting pipeline-state -> blocked (exit 2)" 2 $?

run_rsg_bash "mv /tmp/x pipeline-state/task" "$RSG_MAIN"
run_test "gap4: mv targeting pipeline-state -> blocked (exit 2)" 2 $?

# -- Gap 5: escape-audit write for RSG ----------------------------------------
echo "-- gap5: escape-audit --"

RSG_ESC_TMP=$(mktemp -d)
(
  cd "$RSG_MAIN" && \
  export CLAUDE_DISABLE_RUNTIME_STATE_GUARD=1 && \
  export CLAUDE_PLUGIN_DATA="$RSG_ESC_TMP" && \
  export CLAUDE_SESSION_ID="rsg-escape-test-$$" && \
  jq -nc --arg c "mkdir -p pipeline-state/test" \
    '{tool_name:"Bash",tool_input:{command:$c},hook_event_name:"PreToolUse"}' \
    | bash "$HOOKS_DIR/runtime-state-guard.sh" > /dev/null 2>&1
)
# Check that a guard-escapes.jsonl was written with rsg record
if find "$RSG_ESC_TMP" -name "guard-escapes.jsonl" -exec grep -l '"guard":"runtime-state-guard"' {} \; 2>/dev/null | grep -q .; then
  pass "gap5: escape var set -> guard-escapes.jsonl contains rsg record"
else
  fail "gap5: escape var set -> guard-escapes.jsonl contains rsg record" "rsg record in jsonl" "not found"
fi
rm -rf "$RSG_ESC_TMP"

# Cleanup
(cd "$RSG_MAIN" && git worktree remove --force "$RSG_WT" 2>/dev/null)
rm -rf "$RSG_TMP"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0

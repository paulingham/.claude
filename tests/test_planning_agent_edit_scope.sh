#!/usr/bin/env bash
# Test the planning-agent-edit-scope.sh PreToolUse hook.
#
# Contract:
# - planning-agent + Edit on <worktree>/pipeline-state/<id>-plan.md  -> exit 0 (allowed)
# - planning-agent + Edit on any other path                          -> exit 2 (blocked)
# - non-planning-agent + Edit on any path                            -> exit 0 (skipped)
# - planning-agent + non-Edit/Write/MultiEdit tool                   -> exit 0 (skipped)
# - planning-agent + traversal attempt that escapes pipeline-state/   -> exit 2 (blocked)
#
# Hook reads stdin JSON (tool_name, subagent_type, tool_input.file_path,
# session_id) — peer hook convention. See hooks/pre-agent-allowlist.sh.
set -uo pipefail

HOOK="${BASH_SOURCE%/*}/../hooks/planning-agent-edit-scope.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

# Resolve worktree root once — the hook resolves files relative to it.
WORKTREE_ROOT=$(git -C "$(dirname "$HOOK")" rev-parse --show-toplevel)

PASS=0
FAIL=0
LOG_DIR=$(mktemp -d)
trap 'rm -rf "$LOG_DIR"' EXIT

# Pre-create a real plan file inside the worktree's pipeline-state so realpath
# resolves it deterministically across test runs without touching state outside
# the worktree (it's already a tracked dir in this branch).
mkdir -p "$WORKTREE_ROOT/pipeline-state"

assert_exit() {
  local expected=$1 actual=$2 label=$3
  if [[ "$expected" -eq "$actual" ]]; then
    echo "  ok: $label"
    PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (expected $expected, got $actual)"
    FAIL=$((FAIL + 1))
  fi
}

run_hook() {
  local subagent=$1 tool=$2 path=$3 session="${4:-test-session}"
  local payload
  payload=$(jq -nc \
    --arg t "$tool" \
    --arg s "$subagent" \
    --arg p "$path" \
    --arg sid "$session" \
    '{tool_name:$t, subagent_type:$s, session_id:$sid, tool_input:{file_path:$p}}')
  HOME="$LOG_DIR" \
    bash "$HOOK" <<< "$payload" >/dev/null 2>&1
  echo $?
}

ALLOWED_PATH="$WORKTREE_ROOT/pipeline-state/wave3-I-plan.md"
NESTED_PATH="$WORKTREE_ROOT/pipeline-state/abc-123-plan.md"

echo "Test 1: planning-agent allowed on pipeline-state plan file"
rc=$(run_hook "planning-agent" "Edit" "$ALLOWED_PATH")
assert_exit 0 "$rc" "Edit on pipeline-state/<id>-plan.md returns 0"

echo "Test 2: planning-agent blocked on non-plan file"
rc=$(run_hook "planning-agent" "Edit" "$WORKTREE_ROOT/src/foo.py")
assert_exit 2 "$rc" "Edit on src/foo.py returns 2"

echo "Test 3: planning-agent blocked on Write of arbitrary file"
rc=$(run_hook "planning-agent" "Write" "$WORKTREE_ROOT/scripts/run.sh")
assert_exit 2 "$rc" "Write on scripts/run.sh returns 2"

echo "Test 4: non-planning-agent unaffected"
rc=$(run_hook "software-engineer" "Edit" "$WORKTREE_ROOT/src/foo.py")
assert_exit 0 "$rc" "software-engineer Edit anywhere returns 0"

echo "Test 5: planning-agent + non-Edit tool skipped"
rc=$(run_hook "planning-agent" "Read" "$WORKTREE_ROOT/src/foo.py")
assert_exit 0 "$rc" "Read tool not gated"

echo "Test 6: planning-agent on plan file in nested pipeline-state path"
rc=$(run_hook "planning-agent" "MultiEdit" "$NESTED_PATH")
assert_exit 0 "$rc" "MultiEdit on plan file returns 0"

echo "Test 7: planning-agent blocked on plan-like path NOT in pipeline-state/"
rc=$(run_hook "planning-agent" "Edit" "$WORKTREE_ROOT/docs/something-plan.md")
assert_exit 2 "$rc" "Edit on docs/<id>-plan.md returns 2 (must be in pipeline-state/)"

echo "Test 8: planning-agent blocked on traversal escape attempt"
rc=$(run_hook "planning-agent" "Edit" "$WORKTREE_ROOT/pipeline-state/../../etc/passwd-plan.md")
assert_exit 2 "$rc" "Traversal '..' escape blocked"

echo "Test 9: planning-agent blocked on filename with bad characters"
rc=$(run_hook "planning-agent" "Edit" "$WORKTREE_ROOT/pipeline-state/has space-plan.md")
assert_exit 2 "$rc" "Filename with whitespace blocked"

echo "Test 10: malicious session_id is sanitized (no traversal in log path)"
# Even with a traversal session, the hook must not write outside metrics.
rc=$(run_hook "planning-agent" "Edit" "$WORKTREE_ROOT/src/foo.py" "../../etc")
assert_exit 2 "$rc" "Sanitized session id still blocks write"
# Verify no file was created outside the metrics tree
if [[ -e "$LOG_DIR/etc" ]]; then
  echo "  FAIL: traversal session id wrote outside metrics dir"
  FAIL=$((FAIL + 1))
else
  echo "  ok: no traversal write occurred"
  PASS=$((PASS + 1))
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

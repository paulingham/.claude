#!/usr/bin/env bash
# Test the planning-agent-edit-scope.sh PreToolUse hook.
#
# Contract:
# - planning-agent + Edit on pipeline-state/<id>-plan.md  -> exit 0 (allowed)
# - planning-agent + Edit on any other path                -> exit 2 (blocked)
# - non-planning-agent + Edit on any path                  -> exit 0 (skipped)
# - planning-agent + non-Edit/Write/MultiEdit tool         -> exit 0 (skipped)
set -uo pipefail

HOOK="${BASH_SOURCE%/*}/../hooks/planning-agent-edit-scope.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

PASS=0
FAIL=0
LOG_DIR=$(mktemp -d)
trap 'rm -rf "$LOG_DIR"' EXIT

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
  local subagent=$1 tool=$2 path=$3
  CLAUDE_SUBAGENT_TYPE="$subagent" \
  CLAUDE_TOOL_NAME="$tool" \
  CLAUDE_TOOL_INPUT_FILE_PATH="$path" \
  CLAUDE_SESSION_ID="test-session" \
  HOME="$LOG_DIR" \
    bash "$HOOK" >/dev/null 2>&1
  echo $?
}

echo "Test 1: planning-agent allowed on pipeline-state plan file"
rc=$(run_hook "planning-agent" "Edit" "pipeline-state/wave3-I-plan.md")
assert_exit 0 "$rc" "Edit on pipeline-state/<id>-plan.md returns 0"

echo "Test 2: planning-agent blocked on non-plan file"
rc=$(run_hook "planning-agent" "Edit" "src/foo.py")
assert_exit 2 "$rc" "Edit on src/foo.py returns 2"

echo "Test 3: planning-agent blocked on Write of arbitrary file"
rc=$(run_hook "planning-agent" "Write" "scripts/run.sh")
assert_exit 2 "$rc" "Write on scripts/run.sh returns 2"

echo "Test 4: non-planning-agent unaffected"
rc=$(run_hook "software-engineer" "Edit" "src/foo.py")
assert_exit 0 "$rc" "software-engineer Edit anywhere returns 0"

echo "Test 5: planning-agent + non-Edit tool skipped"
rc=$(run_hook "planning-agent" "Read" "src/foo.py")
assert_exit 0 "$rc" "Read tool not gated"

echo "Test 6: planning-agent on plan file in nested pipeline-state path"
rc=$(run_hook "planning-agent" "MultiEdit" "pipeline-state/abc-123-plan.md")
assert_exit 0 "$rc" "MultiEdit on plan file returns 0"

echo "Test 7: planning-agent blocked on plan-like path NOT in pipeline-state/"
rc=$(run_hook "planning-agent" "Edit" "docs/something-plan.md")
assert_exit 2 "$rc" "Edit on docs/<id>-plan.md returns 2 (must be in pipeline-state/)"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

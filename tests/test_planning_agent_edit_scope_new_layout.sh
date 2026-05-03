#!/usr/bin/env bash
# Slice B — planning-agent-edit-scope.sh accepts new-layout plan.md AND legacy form,
# but rejects other basenames in a {task-id}/ subdir. AC #4 + R11.
set -uo pipefail

HOOK="${BASH_SOURCE%/*}/../hooks/planning-agent-edit-scope.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

WORKTREE_ROOT=$(git -C "$(dirname "$HOOK")" rev-parse --show-toplevel)
PASS=0; FAIL=0
LOG_DIR=$(mktemp -d); trap 'rm -rf "$LOG_DIR"' EXIT
mkdir -p "$WORKTREE_ROOT/pipeline-state/t1"

run_hook() {
  local subagent="$1" tool="$2" path="$3"
  local payload
  payload=$(jq -nc --arg t "$tool" --arg s "$subagent" --arg p "$path" \
    '{tool_name:$t, subagent_type:$s, session_id:"test", tool_input:{file_path:$p}}')
  HOME="$LOG_DIR" bash "$HOOK" <<<"$payload" >/dev/null 2>&1
  echo $?
}

assert_exit() {
  local expected=$1 actual=$2 label=$3
  if [[ "$expected" -eq "$actual" ]]; then
    echo "  ok: $label"; PASS=$((PASS + 1))
  else
    echo "  FAIL: $label (expected $expected, got $actual)"; FAIL=$((FAIL + 1))
  fi
}

echo "Test planning_agent_edit_scope_accepts_new_layout_plan_md"
NEW_PLAN="$WORKTREE_ROOT/pipeline-state/t1/plan.md"
rc=$(run_hook "planning-agent" "Edit" "$NEW_PLAN")
assert_exit 0 "$rc" "Edit on pipeline-state/t1/plan.md returns 0"

echo "Test planning_agent_edit_scope_accepts_legacy_plan_md"
LEGACY_PLAN="$WORKTREE_ROOT/pipeline-state/t1-plan.md"
rc=$(run_hook "planning-agent" "Edit" "$LEGACY_PLAN")
assert_exit 0 "$rc" "Edit on legacy pipeline-state/t1-plan.md returns 0"

echo "Test planning_agent_edit_scope_rejects_other_md_under_subdir"
OTHER_FILE="$WORKTREE_ROOT/pipeline-state/t1/build.md"
rc=$(run_hook "planning-agent" "Edit" "$OTHER_FILE")
assert_exit 2 "$rc" "Edit on pipeline-state/t1/build.md returns 2"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

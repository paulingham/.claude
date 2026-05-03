#!/usr/bin/env bash
# Slice B — pipeline-state-guard.sh tolerates BOTH layouts during DUAL_PATH soak.
# AC #4. Stub names from per-task-subdirs-plan.md § Failing Test Stubs.
set -uo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
HOOK="$REPO_ROOT/hooks/pipeline-state-guard.sh"
[[ -x "$HOOK" ]] || { echo "FAIL: hook not executable: $HOOK"; exit 1; }

PASS=0; FAIL=0
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude"; ln -s "$REPO_ROOT/hooks" "$TMP/.claude/hooks"

run_guard() {
  local agent_type="$1"
  local payload
  payload=$(jq -nc --arg t "$agent_type" \
    '{tool_name:"Agent", tool_input:{subagent_type:$t}}')
  # cd into TMP so git rev-parse fails and the hook falls back to $HOME/.claude/pipeline-state
  (cd "$TMP" && HOME="$TMP" CLAUDE_HOOK_PROFILE=standard bash "$HOOK" <<<"$payload") >/dev/null 2>&1
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

echo "Test guard_passes_when_new_layout_pipeline_exists"
mkdir -p "$TMP/.claude/pipeline-state/t1"
printf -- '---\ntask_id: t1\nverdict: in_progress\n---\n' > "$TMP/.claude/pipeline-state/t1/pipeline.md"
rc=$(run_guard "software-engineer")
assert_exit 0 "$rc" "guard_passes_when_new_layout_pipeline_exists"

echo "Test guard_passes_when_legacy_layout_pipeline_exists"
rm -rf "$TMP/.claude/pipeline-state"
mkdir -p "$TMP/.claude/pipeline-state"
printf -- '---\ntask_id: t1\nverdict: in_progress\n---\n' > "$TMP/.claude/pipeline-state/t1-pipeline.md"
rc=$(run_guard "software-engineer")
assert_exit 0 "$rc" "guard_passes_when_legacy_layout_pipeline_exists"

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1

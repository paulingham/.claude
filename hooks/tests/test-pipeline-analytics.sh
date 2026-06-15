#!/usr/bin/env bash
# CI-BRIDGE: run by tests/shell/bridge_pipeline_analytics.bats
# Tests for pipeline-analytics.sh ordering invariant (slice-4).
# AC-4.1: analytics exits 0 when state present at call time.
# AC-4.1: analytics exits 1 when state already cleaned (strict invariant preserved).
#
# Run from repo root: bash hooks/tests/test-pipeline-analytics.sh
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

echo "=== pipeline-analytics (ordering) Test Harness ==="
echo ""

# -- Syntax check -------------------------------------------------------------
echo "-- syntax --"
bash -n "$HOOKS_DIR/pipeline-analytics.sh" > /dev/null 2>&1
run_test "syntax valid" 0 $?

# -- Setup hermetic HARNESS_DATA + pipeline state ----------------------------
PA_TMP=$(mktemp -d)
PA_TASK_ID="test-analytics-task-$$"
PA_STATE_DIR="$PA_TMP/pipeline-state/$PA_TASK_ID"
mkdir -p "$PA_STATE_DIR"

# Write a minimal pipeline.md with required YAML frontmatter
cat > "$PA_STATE_DIR/pipeline.md" <<'PIPELINEMD'
---
task_id: test-analytics-task
phase: ship
plan: completed
build: completed
review: completed
test: completed
ship: completed
---

# Pipeline: test-analytics-task

## Status
All phases complete.
PIPELINEMD

# -- AC-4.1: analytics exits 0 when state present at call time ---------------
echo "-- ordering: state present --"
(
  # Use CLAUDE_PLUGIN_DATA: harness-paths.sh resolves HARNESS_DATA from CLAUDE_PLUGIN_DATA,
  # overriding any pre-existing HARNESS_DATA env var. This is the correct override mechanism.
  export CLAUDE_PLUGIN_DATA="$PA_TMP"
  bash "$HOOKS_DIR/pipeline-analytics.sh" "$PA_TASK_ID" > /dev/null 2>&1
)
run_test "ordering: analytics exits 0 when state present at call time" 0 $?

# -- AC-4.1: analytics exits 1 when state already cleaned (strict invariant) --
echo "-- ordering: state already cleaned --"
rm -rf "$PA_STATE_DIR"
(
  export CLAUDE_PLUGIN_DATA="$PA_TMP"
  bash "$HOOKS_DIR/pipeline-analytics.sh" "$PA_TASK_ID" > /dev/null 2>&1
)
run_test "ordering: analytics exits 1 when state already cleaned (strict invariant preserved)" 1 $?

# -- AC-4.1 / workstream: workstream-form task-id (workstreams/{ws}/{task}) ----
# The script parses workstreams/{ws}/{task-id} before sanitization (lines 24-31).
# This path is used by CLAUDE_WORKSTREAM-scoped pipelines and must resolve
# TASK_STATE_DIR as pipeline-state/workstreams/{ws}/{task}/pipeline.md.
# A broken parse collapses the path and causes exit 1 even when state exists.
echo "-- workstream-form task-id --"

PA_WS_TMP=$(mktemp -d)
PA_WS="my-workstream"
PA_WS_TASK="analytics-ws-task-$$"
PA_WS_STATE_DIR="$PA_WS_TMP/pipeline-state/workstreams/$PA_WS/$PA_WS_TASK"
mkdir -p "$PA_WS_STATE_DIR"

cat > "$PA_WS_STATE_DIR/pipeline.md" <<'WSPIPELINEMD'
---
task_id: analytics-ws-task
phase: ship
plan: completed
build: completed
review: completed
test: completed
ship: completed
---

# Pipeline: analytics-ws-task

## Status
All phases complete.
WSPIPELINEMD

(
  export CLAUDE_PLUGIN_DATA="$PA_WS_TMP"
  bash "$HOOKS_DIR/pipeline-analytics.sh" "workstreams/$PA_WS/$PA_WS_TASK" > /dev/null 2>&1
)
run_test "workstream-form: analytics exits 0 when workstream state present" 0 $?

# Confirm strict exit 1 when workstream state is cleaned
rm -rf "$PA_WS_STATE_DIR"
(
  export CLAUDE_PLUGIN_DATA="$PA_WS_TMP"
  bash "$HOOKS_DIR/pipeline-analytics.sh" "workstreams/$PA_WS/$PA_WS_TASK" > /dev/null 2>&1
)
run_test "workstream-form: analytics exits 1 when workstream state already cleaned" 1 $?

rm -rf "$PA_WS_TMP"

# -- Cleanup ------------------------------------------------------------------
rm -rf "$PA_TMP"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0

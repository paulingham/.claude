#!/usr/bin/env bash
# Nested-Pipeline Isolation Tests (Story 6a)
# Verifies the env-var contract in skills/internal-eval/run/ISOLATION.md.
# Each patched hook gets two tests: isolated-path (env set) + backward-compat (env unset).

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

run_test() {
  local name="$1" expected="$2" actual="$3"
  [[ "$actual" -eq "$expected" ]] && pass "$name" || fail "$name" "$expected" "$actual"
}

mk_tmp_home() {
  local tmp; tmp=$(mktemp -d)
  mkdir -p "$tmp/.claude/pipeline-state" "$tmp/.claude/learning" "$tmp/.claude/metrics"
  # Symlink the full hooks dir so `source ~/.claude/hooks/hook-profile.sh` resolves
  # even when the hook is invoked under an isolated $HOME.
  ln -s "$HOOKS_DIR" "$tmp/.claude/hooks"
  # Symlink skills for SQLite live-writer path (observation-capture uses it)
  ln -s "$HOOKS_DIR/../skills" "$tmp/.claude/skills"
  echo "$tmp"
}

echo "=== Nested-Pipeline Isolation Test Harness (Story 6a) ==="
echo ""

# ---------------------------------------------------------------------------
# Test 1: pipeline-state-guard — CLAUDE_PIPELINE_BYPASS=1 emits [guard] bypass
# ---------------------------------------------------------------------------
echo "-- pipeline-state-guard.sh --"

HOME_A=$(mk_tmp_home)
# No pipeline state file present. Without bypass, write-capable agent is blocked (exit 2).
INPUT='{"tool_name":"Agent","tool_input":"{\"subagent_type\":\"software-engineer\"}"}'
HOME="$HOME_A" bash "$HOOKS_DIR/pipeline-state-guard.sh" <<< "$INPUT" >/dev/null 2>&1
run_test "guard: no env, no pipeline state -> blocks (exit 2)" 2 $?

# With bypass=1, should exit 0 AND emit [guard] bypass line with EVAL_RUN_ID + EVAL_CASE_ID.
STDERR_OUT=$(HOME="$HOME_A" CLAUDE_PIPELINE_BYPASS=1 EVAL_RUN_ID=run-x EVAL_CASE_ID=case-y \
  bash "$HOOKS_DIR/pipeline-state-guard.sh" <<< "$INPUT" 2>&1 >/dev/null)
BYPASS_RC=$?
run_test "guard: bypass=1 -> exit 0" 0 $BYPASS_RC
if echo "$STDERR_OUT" | grep -q "\[guard\] bypass: EVAL_RUN_ID=run-x EVAL_CASE_ID=case-y"; then
  pass "guard: bypass emits audit line with EVAL_RUN_ID + EVAL_CASE_ID"
else
  fail "guard: bypass emits audit line" "[guard] bypass: ..." "${STDERR_OUT:-<empty>}"
fi

# Backward-compat: when bypass unset AND pipeline state exists, exit 0 unchanged.
touch "$HOME_A/.claude/pipeline-state/existing-pipeline.md"
HOME="$HOME_A" bash "$HOOKS_DIR/pipeline-state-guard.sh" <<< "$INPUT" >/dev/null 2>&1
run_test "guard: no env + pipeline state present -> allow (exit 0)" 0 $?

rm -rf "$HOME_A"
echo ""

# ---------------------------------------------------------------------------
# Test 2: subagent-stop-trajectory — CLAUDE_PIPELINE_TASK_ID skips fs scan
# ---------------------------------------------------------------------------
echo "-- subagent-stop-trajectory.sh --"

HOME_B=$(mk_tmp_home)
# Seed an outer pipeline state file so auto-detection WOULD pick "outer-task".
cat > "$HOME_B/.claude/pipeline-state/outer-task-pipeline.md" <<EOF
---
task_id: outer-task
verdict: in_progress
---
EOF

# Env var forces inner-task → trajectory goes to inner-task, NOT outer-task.
HOME="$HOME_B" CLAUDE_PIPELINE_TASK_ID="inner-task" \
  bash "$HOOKS_DIR/subagent-stop-trajectory.sh" <<< '{"subagent_type":"test-agent"}' >/dev/null 2>&1
run_test "trajectory: CLAUDE_PIPELINE_TASK_ID set -> exit 0" 0 $?

if [[ -f "$HOME_B/.claude/pipeline-state/inner-task-trajectory.jsonl" ]]; then
  pass "trajectory: env var routes to inner-task-trajectory.jsonl"
else
  fail "trajectory: env var routes to inner-task-trajectory.jsonl" "file exists" "not found"
fi
if [[ ! -f "$HOME_B/.claude/pipeline-state/outer-task-trajectory.jsonl" ]]; then
  pass "trajectory: outer-task-trajectory.jsonl NOT written (scan skipped)"
else
  fail "trajectory: outer-task-trajectory.jsonl NOT written" "absent" "present"
fi

# Backward-compat: no env var → auto-detect from pipeline-state → outer-task.
rm -f "$HOME_B/.claude/pipeline-state/inner-task-trajectory.jsonl"
HOME="$HOME_B" bash "$HOOKS_DIR/subagent-stop-trajectory.sh" <<< '{"subagent_type":"test-agent"}' >/dev/null 2>&1
if [[ -f "$HOME_B/.claude/pipeline-state/outer-task-trajectory.jsonl" ]]; then
  pass "trajectory: no env var -> auto-detect -> outer-task (unchanged)"
else
  fail "trajectory: no env var -> auto-detect -> outer-task" "file exists" "not found"
fi

rm -rf "$HOME_B"
echo ""

# ---------------------------------------------------------------------------
# Test 3: observation-capture — CLAUDE_PROJECT_HASH redirect
# ---------------------------------------------------------------------------
echo "-- observation-capture.sh --"

HOME_C=$(mk_tmp_home)
OVERRIDE_HASH="nested-inner-hash-abcd"

# Env var set → observation lands under overridden hash.
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/a.ts"},"tool_output":{}}' | \
  HOME="$HOME_C" CLAUDE_SESSION_ID="iso-sess-1" CLAUDE_PROJECT_HASH="$OVERRIDE_HASH" \
  bash "$HOOKS_DIR/observation-capture.sh" 2>/dev/null
run_test "observation: CLAUDE_PROJECT_HASH set -> exit 0" 0 $?

OVERRIDE_OBS="$HOME_C/.claude/learning/$OVERRIDE_HASH/observations.jsonl"
if [[ -f "$OVERRIDE_OBS" ]]; then
  pass "observation: record lands in overridden learning/<hash>/observations.jsonl"
  RECORDED_HASH=$(jq -r '.project_hash // empty' "$OVERRIDE_OBS" | tail -1)
  if [[ "$RECORDED_HASH" == "$OVERRIDE_HASH" ]]; then
    pass "observation: record's project_hash field matches override"
  else
    fail "observation: record's project_hash field matches override" "$OVERRIDE_HASH" "$RECORDED_HASH"
  fi
else
  fail "observation: record lands in overridden path" "file exists" "not found at $OVERRIDE_OBS"
fi

# Backward-compat: env var unset → computed project_hash path (NOT override).
# Use a hermetic git repo so the computed hash is deterministic and NOT the override.
COMPAT_HOME_TMP=$(mktemp -d); COMPAT_REPO="$COMPAT_HOME_TMP/repo"; COMPAT_FAKE_HOME=$(mk_tmp_home)
git init -q "$COMPAT_REPO" 2>/dev/null
(cd "$COMPAT_REPO" && git remote add origin "https://example.invalid/iso-compat.git" 2>/dev/null)
COMPAT_HASH=$(cd "$COMPAT_REPO" && source "$HOOKS_DIR/_lib/project-hash.sh" && _project_hash --fallback "local")

echo '{"tool_name":"Read","tool_input":{"file_path":"/tmp/b.ts"},"tool_output":{}}' | \
  (cd "$COMPAT_REPO" && HOME="$COMPAT_FAKE_HOME" CLAUDE_SESSION_ID="iso-sess-2" \
    bash "$HOOKS_DIR/observation-capture.sh" 2>/dev/null)
COMPAT_OBS="$COMPAT_FAKE_HOME/.claude/learning/$COMPAT_HASH/observations.jsonl"
if [[ -f "$COMPAT_OBS" ]]; then
  pass "observation: no env var -> computed hash path (unchanged)"
else
  fail "observation: no env var -> computed hash path" "file exists" "not found at $COMPAT_OBS"
fi
rm -rf "$HOME_C" "$COMPAT_HOME_TMP" "$COMPAT_FAKE_HOME"
echo ""

# ---------------------------------------------------------------------------
# Test 4: auto-learn-gate — CLAUDE_DISABLE_AUTO_LEARN=1 fast-exits
# ---------------------------------------------------------------------------
echo "-- auto-learn-gate.sh (disable flag lock-in) --"

# Confirm fast-exit behavior: the hook must delegate to check_bypass_gate for the disable flag.
# (Updated from raw-literal grep: GP-19 migrated inline [[ "${CLAUDE_DISABLE_AUTO_LEARN:-0}" == "1" ]]
# to check_bypass_gate "CLAUDE_DISABLE_AUTO_LEARN" && exit 0, grouped with sources lines 10-11.
# The structural invariant is that the bypass check still short-circuits early — the sourced helper
# call is the new shape. Do NOT revert to the raw env literal — that would re-introduce the dup.)
if grep -q 'check_bypass_gate "CLAUDE_DISABLE_AUTO_LEARN"' "$HOOKS_DIR/auto-learn-gate.sh"; then
  pass "auto-learn-gate: bypass check delegates to check_bypass_gate CLAUDE_DISABLE_AUTO_LEARN"
else
  fail "auto-learn-gate: bypass check delegates to check_bypass_gate CLAUDE_DISABLE_AUTO_LEARN" \
    "check_bypass_gate call present" "not found"
fi

# Runtime check: with flag set, no trigger banner is emitted even with full state setup.
DIS_HOME=$(mk_tmp_home)
DIS_HASH="test-iso-disable-$$"
DIS_LEARN="$DIS_HOME/.claude/learning/$DIS_HASH"
mkdir -p "$DIS_LEARN/instincts"
for i in 1 2 3; do
  printf '{"record_type":"pipeline","timestamp":"2026-04-24T00:00:%02dZ","pipeline_id":"p%d","classification":"feature","phases":{"build":{"verdict":"BUILD_COMPLETE"}},"rework":false}\n' "$i" "$i" >> "$DIS_LEARN/observations.jsonl"
done
DIS_OUT=$(HOME="$DIS_HOME" CLAUDE_DISABLE_AUTO_LEARN=1 CLAUDE_LEARN_TEST_HASH="$DIS_HASH" \
  bash "$HOOKS_DIR/auto-learn-gate.sh" <<< '{}' 2>&1)
DIS_RC=$?
run_test "auto-learn-gate: disabled exits 0 (runtime)" 0 $DIS_RC
if echo "$DIS_OUT" | grep -q "Triggered"; then
  fail "auto-learn-gate: disabled suppresses trigger banner" "no trigger" "triggered"
else
  pass "auto-learn-gate: disabled suppresses trigger banner"
fi
rm -rf "$DIS_HOME"
echo ""

# ---------------------------------------------------------------------------
# Test 5: cost-tracker — EVAL_RUN_ID + EVAL_CASE_ID tag records
# ---------------------------------------------------------------------------
echo "-- cost-tracker.sh --"

CT_HOME=$(mk_tmp_home)
# shellcheck source=../_lib/state-dir.sh
source "$HOOKS_DIR/_lib/state-dir.sh"
_ensure_state_dir
MY_PID="$$"
echo "cost-iso-sess" > "$(_state_path "session-${MY_PID}")"
echo "$(( $(date +%s) - 30 ))" > "$(_state_path "session-start-${MY_PID}")"

# Both vars set → record includes eval_run_id + eval_case_id.
echo '{"stop_hook_active": false}' | \
  HOME="$CT_HOME" EVAL_RUN_ID="run-iso-1" EVAL_CASE_ID="case-iso-A" \
  bash "$HOOKS_DIR/cost-tracker.sh" 2>/dev/null
run_test "cost-tracker: both eval vars -> exit 0" 0 $?

CT_FILE="$CT_HOME/.claude/metrics/costs.jsonl"
if [[ -f "$CT_FILE" ]]; then
  LAST=$(tail -1 "$CT_FILE")
  RUN=$(echo "$LAST" | jq -r '.eval_run_id // empty')
  CASE=$(echo "$LAST" | jq -r '.eval_case_id // empty')
  if [[ "$RUN" == "run-iso-1" && "$CASE" == "case-iso-A" ]]; then
    pass "cost-tracker: record tagged with eval_run_id + eval_case_id"
  else
    fail "cost-tracker: record tagged with eval vars" "run-iso-1/case-iso-A" "$RUN/$CASE"
  fi
  # event=session_end preserved
  EVENT=$(echo "$LAST" | jq -r '.event // empty')
  [[ "$EVENT" == "session_end" ]] && pass "cost-tracker: event=session_end preserved with eval tags" \
    || fail "cost-tracker: event=session_end preserved" "session_end" "$EVENT"
else
  fail "cost-tracker: record appended with eval vars" "file exists" "not found"
fi

# Backward-compat: neither var set → record has NO eval fields.
rm -f "$CT_FILE"
echo "cost-iso-sess-2" > "$(_state_path "session-${MY_PID}")"
echo '{"stop_hook_active": false}' | \
  HOME="$CT_HOME" bash "$HOOKS_DIR/cost-tracker.sh" 2>/dev/null
if [[ -f "$CT_FILE" ]]; then
  LAST=$(tail -1 "$CT_FILE")
  HAS_RUN=$(echo "$LAST" | jq 'has("eval_run_id")')
  HAS_CASE=$(echo "$LAST" | jq 'has("eval_case_id")')
  if [[ "$HAS_RUN" == "false" && "$HAS_CASE" == "false" ]]; then
    pass "cost-tracker: no env vars -> no eval_run_id/eval_case_id keys (unchanged)"
  else
    fail "cost-tracker: no env vars -> no eval keys" "false/false" "$HAS_RUN/$HAS_CASE"
  fi
fi

# Only one var set (asymmetric) → still no eval keys (require BOTH).
rm -f "$CT_FILE"
echo "cost-iso-sess-3" > "$(_state_path "session-${MY_PID}")"
echo '{"stop_hook_active": false}' | \
  HOME="$CT_HOME" EVAL_RUN_ID="run-only" \
  bash "$HOOKS_DIR/cost-tracker.sh" 2>/dev/null
if [[ -f "$CT_FILE" ]]; then
  LAST=$(tail -1 "$CT_FILE")
  HAS_RUN=$(echo "$LAST" | jq 'has("eval_run_id")')
  if [[ "$HAS_RUN" == "false" ]]; then
    pass "cost-tracker: only EVAL_RUN_ID set (no case id) -> no eval keys"
  else
    fail "cost-tracker: asymmetric vars -> no eval keys" "false" "$HAS_RUN"
  fi
fi

rm -f "$(_state_path "session-${MY_PID}")" "$(_state_path "session-start-${MY_PID}")"
rm -rf "$CT_HOME"
echo ""

# ---------------------------------------------------------------------------
# Test 6: Integration — simultaneous outer + inner, no cross-contamination
# ---------------------------------------------------------------------------
echo "-- integration: outer + inner simultaneous --"

OUTER_HOME=$(mk_tmp_home)
INNER_HOME=$(mk_tmp_home)
# Seed outer pipeline state.
cat > "$OUTER_HOME/.claude/pipeline-state/outer-pipeline.md" <<EOF
---
task_id: outer
verdict: in_progress
---
EOF

# Outer observation under outer's home.
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/outer.ts"},"tool_output":{}}' | \
  HOME="$OUTER_HOME" CLAUDE_SESSION_ID="outer-sess" CLAUDE_PROJECT_HASH="outer-hash" \
  bash "$HOOKS_DIR/observation-capture.sh" 2>/dev/null

# Inner observation with isolation env vars under inner's home.
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/inner.ts"},"tool_output":{}}' | \
  HOME="$INNER_HOME" CLAUDE_SESSION_ID="inner-sess" CLAUDE_PROJECT_HASH="inner-hash" \
  bash "$HOOKS_DIR/observation-capture.sh" 2>/dev/null

# Inner trajectory
HOME="$INNER_HOME" CLAUDE_PIPELINE_TASK_ID="inner-task" \
  bash "$HOOKS_DIR/subagent-stop-trajectory.sh" <<< '{"subagent_type":"test"}' >/dev/null 2>&1

# Assertions
OUTER_OBS="$OUTER_HOME/.claude/learning/outer-hash/observations.jsonl"
INNER_OBS="$INNER_HOME/.claude/learning/inner-hash/observations.jsonl"
if [[ -f "$OUTER_OBS" ]] && [[ -f "$INNER_OBS" ]] && \
   ! grep -q "inner" "$OUTER_OBS" && ! grep -q "outer" "$INNER_OBS"; then
  pass "integration: outer + inner observations land in separate paths, no cross-contamination"
else
  fail "integration: observations isolated" "separate files, no overlap" "contamination detected"
fi

# Outer pipeline-state untouched by inner
OUTER_RESIDUE=$(find "$OUTER_HOME/.claude/pipeline-state" -name "inner*" -o -name "*inner-task*" 2>/dev/null)
if [[ -z "$OUTER_RESIDUE" ]]; then
  pass "integration: outer pipeline-state has zero inner residue"
else
  fail "integration: outer pipeline-state has zero inner residue" "no inner files" "$OUTER_RESIDUE"
fi

# Inner trajectory went to inner's home
if [[ -f "$INNER_HOME/.claude/pipeline-state/inner-task-trajectory.jsonl" ]]; then
  pass "integration: inner trajectory in inner's pipeline-state"
else
  fail "integration: inner trajectory in inner's pipeline-state" "file exists" "not found"
fi

rm -rf "$OUTER_HOME" "$INNER_HOME"
echo ""

# ---------------------------------------------------------------------------
# Test 7: Kill-mid-run — outer pipeline-state has zero inner residue
# ---------------------------------------------------------------------------
echo "-- kill-mid-run --"

OUTER2_HOME=$(mk_tmp_home)
# Seed outer state.
cat > "$OUTER2_HOME/.claude/pipeline-state/outer2-pipeline.md" <<EOF
---
task_id: outer2
verdict: in_progress
---
EOF
SNAP_BEFORE=$(find "$OUTER2_HOME/.claude/pipeline-state" -type f | sort)

# Simulate inner pipeline doing work with BYPASS=1 then dying mid-run.
HOME="$OUTER2_HOME" CLAUDE_PIPELINE_BYPASS=1 EVAL_RUN_ID=kill-run EVAL_CASE_ID=kill-case \
  bash "$HOOKS_DIR/pipeline-state-guard.sh" \
  <<< '{"tool_name":"Agent","tool_input":"{\"subagent_type\":\"software-engineer\"}"}' \
  >/dev/null 2>&1
# (Simulated kill: inner just stops here. No trajectory/obs written because those
# are triggered by different events. The guard should have created ZERO files.)

SNAP_AFTER=$(find "$OUTER2_HOME/.claude/pipeline-state" -type f | sort)
if [[ "$SNAP_BEFORE" == "$SNAP_AFTER" ]]; then
  pass "kill-mid-run: outer pipeline-state unchanged after killed inner"
else
  fail "kill-mid-run: outer pipeline-state unchanged" "no new files" "$(diff <(echo "$SNAP_BEFORE") <(echo "$SNAP_AFTER"))"
fi

# And there's no eval-{run-id}-* file anywhere under outer
EVAL_RESIDUE=$(find "$OUTER2_HOME/.claude/pipeline-state" -name "eval-kill-run*" 2>/dev/null)
if [[ -z "$EVAL_RESIDUE" ]]; then
  pass "kill-mid-run: no eval-{run-id}-* residue"
else
  fail "kill-mid-run: no eval-{run-id}-* residue" "absent" "$EVAL_RESIDUE"
fi

rm -rf "$OUTER2_HOME"
echo ""

# ---------------------------------------------------------------------------
# Test 8: learning-gc — CLAUDE_PROJECT_HASH redirects archive path
# ---------------------------------------------------------------------------
echo "-- learning-gc.sh --"

GC_HOME=$(mk_tmp_home)
GC_OVERRIDE_HASH="gc-iso-hash-xyz"
GC_LEARN_DIR="$GC_HOME/.claude/learning/$GC_OVERRIDE_HASH"
mkdir -p "$GC_LEARN_DIR"
# Seed an old observation (>90 days) under the OVERRIDE hash dir.
OLD_TS=$(/opt/homebrew/bin/python3 -c "from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(days=120)).isoformat())")
printf '{"timestamp":"%s","kind":"old"}\n' "$OLD_TS" > "$GC_LEARN_DIR/observations.jsonl"

# Run learning-gc with CLAUDE_PROJECT_HASH set → archive should land under override.
HOME="$GC_HOME" CLAUDE_PROJECT_HASH="$GC_OVERRIDE_HASH" \
  bash "$HOOKS_DIR/learning-gc.sh" >/dev/null 2>&1
run_test "learning-gc: CLAUDE_PROJECT_HASH set -> exit 0" 0 $?

if [[ -d "$GC_LEARN_DIR/archive" ]]; then
  pass "learning-gc: archive created under overridden hash dir"
else
  fail "learning-gc: archive created under overridden hash dir" "directory exists" "not found at $GC_LEARN_DIR/archive"
fi

# Confirm NO archive was created under any computed-hash dir (only override should be touched).
OTHER_DIRS=$(find "$GC_HOME/.claude/learning" -maxdepth 1 -mindepth 1 -type d ! -name "$GC_OVERRIDE_HASH" 2>/dev/null)
if [[ -z "$OTHER_DIRS" ]]; then
  pass "learning-gc: no archive under git-remote-based hash (override honoured)"
else
  fail "learning-gc: only override hash dir touched" "no other dirs" "$OTHER_DIRS"
fi

rm -rf "$GC_HOME"
echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -gt 0 ]] && exit 1
exit 0

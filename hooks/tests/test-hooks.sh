#!/usr/bin/env bash
# Hook Test Harness — tests all Claude Code hooks with representative inputs
# Run from ~/.claude/: bash hooks/tests/test-hooks.sh
# Exit 0 if all pass, exit 1 if any fail.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

# When the test spawns a hook via `bash hook.sh`, the hook's PPID = this script's PID.
# So session temp files are keyed by $$ (this script's PID), not $PPID.
MY_PID="$$"

pass() { echo "  PASS: $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  FAIL: $1 (expected=$2, got=$3)"; FAIL=$(( FAIL + 1 )); }

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

echo "=== Hook Test Harness ==="
echo ""

# -- hook-profile tests ------------------------------------------------------
echo "-- hook-profile.sh --"

source "$HOOKS_DIR/hook-profile.sh"

CLAUDE_HOOK_PROFILE=minimal check_hook_profile "minimal"
run_test "profile=minimal, required=minimal -> allow" 0 $?

CLAUDE_HOOK_PROFILE=minimal check_hook_profile "standard"
run_test "profile=minimal, required=standard -> skip" 1 $?

CLAUDE_HOOK_PROFILE=standard check_hook_profile "standard"
run_test "profile=standard, required=standard -> allow" 0 $?

CLAUDE_HOOK_PROFILE=strict check_hook_profile "standard"
run_test "profile=strict, required=standard -> allow" 0 $?

unset CLAUDE_HOOK_PROFILE
check_hook_profile "standard"
run_test "profile=unset (default=standard), required=standard -> allow" 0 $?

echo ""

# -- loop-guard tests --------------------------------------------------------
echo "-- loop-guard.sh --"

source "$HOOKS_DIR/loop-guard.sh"

# Clear any existing guard file for test isolation
rm -f "/tmp/claude-hook-guard/test-loop-guard-hook"

LOOP_FAILED=false
for i in $(seq 1 11); do
  check_loop_guard "test-loop-guard-hook" 10 60
  exit_code=$?
  if [[ $i -le 10 && $exit_code -ne 0 ]]; then
    fail "loop-guard call $i of 10 (within limit)" 0 $exit_code
    LOOP_FAILED=true
    break
  elif [[ $i -eq 11 && $exit_code -ne 1 ]]; then
    fail "loop-guard call 11 (over limit) should return 1" 1 $exit_code
    LOOP_FAILED=true
    break
  fi
done
if [[ "$LOOP_FAILED" == "false" ]]; then
  pass "loop-guard: 10 calls allowed, 11th blocked"
fi

echo ""

# -- orchestrator-discipline tests -------------------------------------------
echo "-- orchestrator-discipline.sh --"

echo '{"tool_name":"Write","tool_input":{"file_path":"src/foo.ts"},"hook_event_name":"PreToolUse"}' | bash "$HOOKS_DIR/orchestrator-discipline.sh" > /dev/null 2>&1
run_test "orchestrator-discipline: .ts file -> block (exit 2)" 2 $?

echo '{"tool_name":"Write","tool_input":{"file_path":"rules/foo.md"},"hook_event_name":"PreToolUse"}' | bash "$HOOKS_DIR/orchestrator-discipline.sh" > /dev/null 2>&1
run_test "orchestrator-discipline: .md file -> allow (exit 0)" 0 $?

echo '{"tool_name":"Write","tool_input":{"file_path":""},"hook_event_name":"PreToolUse"}' | bash "$HOOKS_DIR/orchestrator-discipline.sh" > /dev/null 2>&1
run_test "orchestrator-discipline: empty path -> allow (exit 0)" 0 $?

echo ""

# -- tdd-guard tests ---------------------------------------------------------
echo "-- tdd-guard.sh --"

# Non-source file -> allow
echo '{"tool_name":"Write","tool_input":{"file_path":"README.md"},"hook_event_name":"PreToolUse"}' | bash "$HOOKS_DIR/tdd-guard.sh" > /dev/null 2>&1
run_test "tdd-guard: README.md -> allow (exit 0)" 0 $?

# Empty path -> allow
echo '{"tool_name":"Write","tool_input":{"file_path":""},"hook_event_name":"PreToolUse"}' | bash "$HOOKS_DIR/tdd-guard.sh" > /dev/null 2>&1
run_test "tdd-guard: empty path -> allow (exit 0)" 0 $?

# Test file -> allow
echo '{"tool_name":"Write","tool_input":{"file_path":"src/foo.test.ts"},"hook_event_name":"PreToolUse"}' | bash "$HOOKS_DIR/tdd-guard.sh" > /dev/null 2>&1
run_test "tdd-guard: test file -> allow (exit 0)" 0 $?

# New source file (doesn't exist) -> allow (greenfield)
NONEXISTENT_PATH="/tmp/nonexistent-source-$(date +%s).ts"
echo "{\"tool_name\":\"Write\",\"tool_input\":{\"file_path\":\"$NONEXISTENT_PATH\"},\"hook_event_name\":\"PreToolUse\"}" | bash "$HOOKS_DIR/tdd-guard.sh" > /dev/null 2>&1
run_test "tdd-guard: new source file (not on disk) -> allow (exit 0)" 0 $?

echo ""

# -- auto-pr tests -----------------------------------------------------------
echo "-- auto-pr.sh --"

# On main -> skip
(cd /tmp && git init -q test-auto-pr-$$ 2>/dev/null && cd test-auto-pr-$$ && \
  git checkout -q -b main 2>/dev/null || true && \
  echo '{"stop_hook_active": false}' | BRANCH=main bash "$HOOKS_DIR/auto-pr.sh" > /dev/null 2>&1)
run_test "auto-pr: on main branch -> skip (exit 0)" 0 $?

# No upstream commits -> skip
echo '{"stop_hook_active": false}' | BRANCH=feature/test bash "$HOOKS_DIR/auto-pr.sh" > /dev/null 2>&1
run_test "auto-pr: advisory hook always exits 0" 0 $?

echo ""

# -- observation-capture tests (enriched) ------------------------------------
echo "-- observation-capture.sh (enriched) --"

# Setup: clean session temp files keyed by MY_PID (hook's PPID = this script's PID)
rm -f "/tmp/claude-session-${MY_PID}"
rm -f "/tmp/claude-session-start-${MY_PID}"

# Get the project hash that observation-capture will use
OBS_PROJECT_HASH=$(git remote get-url origin 2>/dev/null | openssl md5 -r 2>/dev/null | awk '{print $1}' || basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")
OBS_FILE="$HOME/.claude/learning/$OBS_PROJECT_HASH/observations.jsonl"

# Test: Enriched fields from env vars
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/test.ts"},"tool_output":{}}' | \
  CLAUDE_SESSION_ID="test-session-123" \
  CLAUDE_PIPELINE_PHASE="build" \
  CLAUDE_AGENT_ROLE="software-engineer" \
  bash "$HOOKS_DIR/observation-capture.sh" 2>/dev/null

if [[ -f "$OBS_FILE" ]]; then
  LAST_LINE=$(tail -1 "$OBS_FILE")

  # Test: session_id present
  SESSION_VAL=$(echo "$LAST_LINE" | jq -r '.session_id // empty')
  if [[ "$SESSION_VAL" == "test-session-123" ]]; then
    pass "observation-capture: session_id from env var"
  else
    fail "observation-capture: session_id from env var" "test-session-123" "$SESSION_VAL"
  fi

  # Test: project field present (human-readable name)
  PROJECT_VAL=$(echo "$LAST_LINE" | jq -r '.project // empty')
  if [[ -n "$PROJECT_VAL" ]]; then
    pass "observation-capture: project field present"
  else
    fail "observation-capture: project field present" "non-empty" "$PROJECT_VAL"
  fi

  # Test: project_hash field present
  HASH_VAL=$(echo "$LAST_LINE" | jq -r '.project_hash // empty')
  if [[ -n "$HASH_VAL" ]]; then
    pass "observation-capture: project_hash field present"
  else
    fail "observation-capture: project_hash field present" "non-empty" "$HASH_VAL"
  fi

  # Test: phase field present
  PHASE_VAL=$(echo "$LAST_LINE" | jq -r '.phase // empty')
  if [[ "$PHASE_VAL" == "build" ]]; then
    pass "observation-capture: phase from env var"
  else
    fail "observation-capture: phase from env var" "build" "$PHASE_VAL"
  fi

  # Test: agent_role field present
  ROLE_VAL=$(echo "$LAST_LINE" | jq -r '.agent_role // empty')
  if [[ "$ROLE_VAL" == "software-engineer" ]]; then
    pass "observation-capture: agent_role from env var"
  else
    fail "observation-capture: agent_role from env var" "software-engineer" "$ROLE_VAL"
  fi

  # Test: outcome defaults to success
  OUTCOME_VAL=$(echo "$LAST_LINE" | jq -r '.outcome // empty')
  if [[ "$OUTCOME_VAL" == "success" ]]; then
    pass "observation-capture: outcome=success (no error)"
  else
    fail "observation-capture: outcome=success (no error)" "success" "$OUTCOME_VAL"
  fi
else
  fail "observation-capture: observations file exists" "file exists" "not found at $OBS_FILE"
  for skip_name in "session_id from env var" "project field present" "project_hash field present" "phase from env var" "agent_role from env var" "outcome=success (no error)"; do
    fail "observation-capture: $skip_name" "file exists" "skipped"
  done
fi

# Test: outcome=error when tool_output.is_error is true
echo '{"tool_name":"Bash","tool_input":{"command":"false"},"tool_output":{"is_error":true}}' | \
  CLAUDE_SESSION_ID="test-session-err" \
  bash "$HOOKS_DIR/observation-capture.sh" 2>/dev/null

if [[ -f "$OBS_FILE" ]]; then
  LAST_LINE=$(tail -1 "$OBS_FILE")
  OUTCOME_VAL=$(echo "$LAST_LINE" | jq -r '.outcome // empty')
  if [[ "$OUTCOME_VAL" == "error" ]]; then
    pass "observation-capture: outcome=error when is_error=true"
  else
    fail "observation-capture: outcome=error when is_error=true" "error" "$OUTCOME_VAL"
  fi
fi

# Test: session start time file created (keyed by MY_PID since hook's PPID = our PID)
if [[ -f "/tmp/claude-session-start-${MY_PID}" ]]; then
  START_TIME=$(cat "/tmp/claude-session-start-${MY_PID}")
  if [[ "$START_TIME" =~ ^[0-9]+$ ]]; then
    pass "observation-capture: session start time file created"
  else
    fail "observation-capture: session start time file created" "numeric timestamp" "$START_TIME"
  fi
else
  fail "observation-capture: session start time file created" "file exists" "not found"
fi

# Test: session_id fallback (generated when env var not set)
rm -f "/tmp/claude-session-${MY_PID}"
echo '{"tool_name":"Read","tool_input":{"file_path":"/tmp/test.ts"},"tool_output":{}}' | \
  bash "$HOOKS_DIR/observation-capture.sh" 2>/dev/null

if [[ -f "/tmp/claude-session-${MY_PID}" ]]; then
  GENERATED_ID=$(cat "/tmp/claude-session-${MY_PID}")
  if [[ -n "$GENERATED_ID" ]]; then
    pass "observation-capture: generates session_id when env var unset"
  else
    fail "observation-capture: generates session_id when env var unset" "non-empty" "$GENERATED_ID"
  fi
else
  fail "observation-capture: generates session_id when env var unset" "temp file exists" "not found"
fi

echo ""


# -- subagent-context tests --------------------------------------------------
echo "-- subagent-context.sh --"

# Cleanup temp file before tests
rm -f /tmp/claude-agent-role

# Test: syntax check
bash -n "$HOOKS_DIR/subagent-context.sh" > /dev/null 2>&1
run_test "subagent-context: syntax valid" 0 $?

# Test: writes agent role to temp file
echo '{"subagent_type":"software-engineer"}' | bash "$HOOKS_DIR/subagent-context.sh" 2>/dev/null
SC_EXIT=$?
run_test "subagent-context: exits 0" 0 $SC_EXIT

if [[ -f /tmp/claude-agent-role ]]; then
  SC_ROLE=$(cat /tmp/claude-agent-role)
  if [[ "$SC_ROLE" == "software-engineer" ]]; then
    pass "subagent-context: writes role to /tmp/claude-agent-role"
  else
    fail "subagent-context: writes role to /tmp/claude-agent-role" "software-engineer" "$SC_ROLE"
  fi
else
  fail "subagent-context: writes role to /tmp/claude-agent-role" "file exists" "not found"
fi

# Test: agent_type fallback field
rm -f /tmp/claude-agent-role
echo '{"agent_type":"infrastructure-engineer"}' | bash "$HOOKS_DIR/subagent-context.sh" 2>/dev/null
if [[ -f /tmp/claude-agent-role ]]; then
  SC_ROLE2=$(cat /tmp/claude-agent-role)
  if [[ "$SC_ROLE2" == "infrastructure-engineer" ]]; then
    pass "subagent-context: reads agent_type as fallback"
  else
    fail "subagent-context: reads agent_type as fallback" "infrastructure-engineer" "$SC_ROLE2"
  fi
else
  fail "subagent-context: reads agent_type as fallback" "file exists" "not found"
fi

# Test: empty input exits 0, no file written
rm -f /tmp/claude-agent-role
echo '{}' | bash "$HOOKS_DIR/subagent-context.sh" 2>/dev/null
SC_EMPTY_EXIT=$?
run_test "subagent-context: empty input exits 0" 0 $SC_EMPTY_EXIT
if [[ ! -f /tmp/claude-agent-role ]]; then
  pass "subagent-context: empty input writes no temp file"
else
  fail "subagent-context: empty input writes no temp file" "no file" "file exists"
fi

# Cleanup
rm -f /tmp/claude-agent-role

echo ""

# -- observation-capture fallback tests (file-based context) ----------------
echo "-- observation-capture.sh (file-based fallbacks) --"

# Test: agent_role fallback from /tmp/claude-agent-role
rm -f "/tmp/claude-session-${MY_PID}"
rm -f "/tmp/claude-session-start-${MY_PID}"
echo "code-reviewer" > /tmp/claude-agent-role

echo '{"tool_name":"Read","tool_input":{"file_path":"/tmp/test.ts"},"tool_output":{}}' | \
  CLAUDE_SESSION_ID="test-fallback-role" \
  bash "$HOOKS_DIR/observation-capture.sh" 2>/dev/null

if [[ -f "$OBS_FILE" ]]; then
  LAST_LINE=$(tail -1 "$OBS_FILE")
  FB_ROLE=$(echo "$LAST_LINE" | jq -r '.agent_role // empty')
  if [[ "$FB_ROLE" == "code-reviewer" ]]; then
    pass "observation-capture: agent_role fallback from temp file"
  else
    fail "observation-capture: agent_role fallback from temp file" "code-reviewer" "$FB_ROLE"
  fi
else
  fail "observation-capture: agent_role fallback from temp file" "file exists" "obs file missing"
fi

# Test: env var takes precedence over temp file
echo "wrong-role" > /tmp/claude-agent-role

echo '{"tool_name":"Read","tool_input":{"file_path":"/tmp/test.ts"},"tool_output":{}}' | \
  CLAUDE_SESSION_ID="test-envvar-precedence" \
  CLAUDE_AGENT_ROLE="correct-role" \
  bash "$HOOKS_DIR/observation-capture.sh" 2>/dev/null

if [[ -f "$OBS_FILE" ]]; then
  LAST_LINE=$(tail -1 "$OBS_FILE")
  PREC_ROLE=$(echo "$LAST_LINE" | jq -r '.agent_role // empty')
  if [[ "$PREC_ROLE" == "correct-role" ]]; then
    pass "observation-capture: env var precedence over temp file for agent_role"
  else
    fail "observation-capture: env var precedence over temp file for agent_role" "correct-role" "$PREC_ROLE"
  fi
else
  fail "observation-capture: env var precedence over temp file for agent_role" "file exists" "obs file missing"
fi

# Test: phase fallback from pipeline state file
OC_PIPELINE_DIR="$HOME/.claude/pipeline-state"
mkdir -p "$OC_PIPELINE_DIR"
OC_TEST_PIPELINE="$OC_PIPELINE_DIR/test-phase-fallback-pipeline.md"
cat > "$OC_TEST_PIPELINE" << 'EOPIPE'
---
task_id: test-phase-fallback
---

## Phases
- Plan: complete
- Build: in_progress
- Review: pending
EOPIPE

rm -f /tmp/claude-agent-role

echo '{"tool_name":"Read","tool_input":{"file_path":"/tmp/test.ts"},"tool_output":{}}' | \
  CLAUDE_SESSION_ID="test-phase-fallback" \
  bash "$HOOKS_DIR/observation-capture.sh" 2>/dev/null

if [[ -f "$OBS_FILE" ]]; then
  LAST_LINE=$(tail -1 "$OBS_FILE")
  FB_PHASE=$(echo "$LAST_LINE" | jq -r '.phase // empty')
  if [[ "$FB_PHASE" == "build" ]]; then
    pass "observation-capture: phase fallback from pipeline state file"
  else
    fail "observation-capture: phase fallback from pipeline state file" "build" "$FB_PHASE"
  fi
else
  fail "observation-capture: phase fallback from pipeline state file" "file exists" "obs file missing"
fi

# Cleanup test pipeline file
rm -f "$OC_TEST_PIPELINE"
rm -f /tmp/claude-agent-role

echo ""

# -- pipeline-analytics tests -----------------------------------------------
echo "-- pipeline-analytics.sh --"

# Test: missing task-id argument
bash "$HOOKS_DIR/pipeline-analytics.sh" 2>/dev/null
run_test "pipeline-analytics: no args -> exit non-zero" 1 $?

# Test: missing pipeline file -> exit 1
bash "$HOOKS_DIR/pipeline-analytics.sh" "nonexistent-task-999" 2>/dev/null
run_test "pipeline-analytics: missing pipeline file -> exit 1" 1 $?

# Test: valid pipeline produces a record
PA_PIPELINE_DIR="$HOME/.claude/pipeline-state"
PA_METRICS_DIR="$HOME/.claude/metrics"
mkdir -p "$PA_PIPELINE_DIR"

PA_TASK_ID="test-analytics-$$"

# Create mock pipeline state files
cat > "$PA_PIPELINE_DIR/${PA_TASK_ID}-pipeline.md" << 'EOPL'
---
task_id: test-analytics
phase: ship
verdict: PIPELINE_COMPLETE
timestamp: 2026-04-01T10:00:00Z
complexity_budget: 7
type: feature
---

## Summary
Test pipeline
EOPL

cat > "$PA_PIPELINE_DIR/${PA_TASK_ID}-build.md" << 'EOBUILD'
---
task_id: test-analytics
phase: build
verdict: BUILD_COMPLETE
timestamp: 2026-04-01T10:01:00Z
---

## Summary
Build done
EOBUILD

cat > "$PA_PIPELINE_DIR/${PA_TASK_ID}-review.md" << 'EOREVIEW'
---
task_id: test-analytics
phase: review
verdict: APPROVE
timestamp: 2026-04-01T10:02:00Z
---

## Summary
Review passed
EOREVIEW

# Record line count before running analytics
PA_METRICS_FILE="$PA_METRICS_DIR/pipelines.jsonl"
LINES_BEFORE=0
if [[ -f "$PA_METRICS_FILE" ]]; then
  LINES_BEFORE=$(wc -l < "$PA_METRICS_FILE" | tr -d ' ')
fi

bash "$HOOKS_DIR/pipeline-analytics.sh" "$PA_TASK_ID" 2>/dev/null
PA_EXIT=$?
run_test "pipeline-analytics: valid pipeline -> exit 0" 0 $PA_EXIT

if [[ -f "$PA_METRICS_FILE" ]]; then
  LINES_AFTER=$(wc -l < "$PA_METRICS_FILE" | tr -d ' ')
  if [[ "$LINES_AFTER" -gt "$LINES_BEFORE" ]]; then
    pass "pipeline-analytics: record appended to pipelines.jsonl"

    PA_LAST=$(tail -1 "$PA_METRICS_FILE")

    # Verify task_id in record
    PA_TASK_VAL=$(echo "$PA_LAST" | jq -r '.task_id // empty')
    if [[ "$PA_TASK_VAL" == "$PA_TASK_ID" ]]; then
      pass "pipeline-analytics: task_id in record"
    else
      fail "pipeline-analytics: task_id in record" "$PA_TASK_ID" "$PA_TASK_VAL"
    fi

    # Verify build phase verdict
    PA_BUILD_VAL=$(echo "$PA_LAST" | jq -r '.phases.build // empty')
    if [[ "$PA_BUILD_VAL" == "BUILD_COMPLETE" ]]; then
      pass "pipeline-analytics: build phase verdict captured"
    else
      fail "pipeline-analytics: build phase verdict captured" "BUILD_COMPLETE" "$PA_BUILD_VAL"
    fi

    # Verify review phase verdict
    PA_REVIEW_VAL=$(echo "$PA_LAST" | jq -r '.phases.review // empty')
    if [[ "$PA_REVIEW_VAL" == "APPROVE" ]]; then
      pass "pipeline-analytics: review phase verdict captured"
    else
      fail "pipeline-analytics: review phase verdict captured" "APPROVE" "$PA_REVIEW_VAL"
    fi

    # Verify type field
    PA_TYPE_VAL=$(echo "$PA_LAST" | jq -r '.type // empty')
    if [[ "$PA_TYPE_VAL" == "feature" ]]; then
      pass "pipeline-analytics: type field captured"
    else
      fail "pipeline-analytics: type field captured" "feature" "$PA_TYPE_VAL"
    fi

    # Verify complexity_budget field
    PA_CPLX_VAL=$(echo "$PA_LAST" | jq -r '.complexity_budget // empty')
    if [[ "$PA_CPLX_VAL" == "7" ]]; then
      pass "pipeline-analytics: complexity_budget captured"
    else
      fail "pipeline-analytics: complexity_budget captured" "7" "$PA_CPLX_VAL"
    fi
  else
    fail "pipeline-analytics: record appended to pipelines.jsonl" "new line" "no new lines"
  fi
else
  fail "pipeline-analytics: pipelines.jsonl created" "file exists" "not found"
fi

# Cleanup test pipeline files
rm -f "$PA_PIPELINE_DIR/${PA_TASK_ID}-pipeline.md"
rm -f "$PA_PIPELINE_DIR/${PA_TASK_ID}-build.md"
rm -f "$PA_PIPELINE_DIR/${PA_TASK_ID}-review.md"

echo ""

# -- cost-tracker tests (enriched) ------------------------------------------
echo "-- cost-tracker.sh (enriched) --"

# Setup: write session temp files keyed by MY_PID (cost-tracker hook's PPID = our PID)
echo "test-cost-session-$$" > "/tmp/claude-session-${MY_PID}"
echo "$(( $(date +%s) - 120 ))" > "/tmp/claude-session-start-${MY_PID}"

CT_METRICS_FILE="$HOME/.claude/metrics/costs.jsonl"
CT_LINES_BEFORE=0
if [[ -f "$CT_METRICS_FILE" ]]; then
  CT_LINES_BEFORE=$(wc -l < "$CT_METRICS_FILE" | tr -d ' ')
fi

echo '{"stop_hook_active": false}' | bash "$HOOKS_DIR/cost-tracker.sh" 2>/dev/null
CT_EXIT=$?
run_test "cost-tracker: exits 0" 0 $CT_EXIT

if [[ -f "$CT_METRICS_FILE" ]]; then
  CT_LINES_AFTER=$(wc -l < "$CT_METRICS_FILE" | tr -d ' ')
  if [[ "$CT_LINES_AFTER" -gt "$CT_LINES_BEFORE" ]]; then
    CT_LAST=$(tail -1 "$CT_METRICS_FILE")

    # Test: session_id present
    CT_SESSION=$(echo "$CT_LAST" | jq -r '.session_id // empty')
    if [[ "$CT_SESSION" == "test-cost-session-$$" ]]; then
      pass "cost-tracker: session_id from temp file"
    else
      fail "cost-tracker: session_id from temp file" "test-cost-session-$$" "$CT_SESSION"
    fi

    # Test: project_hash present
    CT_HASH=$(echo "$CT_LAST" | jq -r '.project_hash // empty')
    if [[ -n "$CT_HASH" ]]; then
      pass "cost-tracker: project_hash present"
    else
      fail "cost-tracker: project_hash present" "non-empty" "$CT_HASH"
    fi

    # Test: duration_s is numeric
    CT_DURATION=$(echo "$CT_LAST" | jq -r '.duration_s // empty')
    if [[ "$CT_DURATION" =~ ^[0-9]+$ ]]; then
      pass "cost-tracker: duration_s is numeric"
    else
      fail "cost-tracker: duration_s is numeric" "numeric" "$CT_DURATION"
    fi

    # Test: tool_calls is numeric
    CT_TOOLS=$(echo "$CT_LAST" | jq -r '.tool_calls // empty')
    if [[ "$CT_TOOLS" =~ ^[0-9]+$ ]]; then
      pass "cost-tracker: tool_calls is numeric"
    else
      fail "cost-tracker: tool_calls is numeric" "numeric" "$CT_TOOLS"
    fi

    # Test: event field still present
    CT_EVENT=$(echo "$CT_LAST" | jq -r '.event // empty')
    if [[ "$CT_EVENT" == "session_end" ]]; then
      pass "cost-tracker: event=session_end preserved"
    else
      fail "cost-tracker: event=session_end preserved" "session_end" "$CT_EVENT"
    fi
  else
    fail "cost-tracker: record appended" "new line" "no new lines"
  fi
fi

# Cleanup session temp files
rm -f "/tmp/claude-session-${MY_PID}"
rm -f "/tmp/claude-session-start-${MY_PID}"

echo ""

# -- session-start-bootstrap tests -------------------------------------------
echo "-- session-start-bootstrap.sh --"

# Test: syntax check
bash -n "$HOOKS_DIR/session-start-bootstrap.sh" > /dev/null 2>&1
run_test "session-start-bootstrap: syntax valid" 0 $?

# Test: stdout contains skill awareness text (the functional output)
SSB_STDOUT=$(bash "$HOOKS_DIR/session-start-bootstrap.sh" 2>/dev/null)
SSB_EXIT=$?
run_test "session-start-bootstrap: exits 0" 0 $SSB_EXIT

if echo "$SSB_STDOUT" | grep -q "SKILL AWARENESS BOOTSTRAP"; then
  pass "session-start-bootstrap: stdout contains SKILL AWARENESS BOOTSTRAP"
else
  fail "session-start-bootstrap: stdout contains SKILL AWARENESS BOOTSTRAP" "present" "missing"
fi

if echo "$SSB_STDOUT" | grep -q "IRON LAWS"; then
  pass "session-start-bootstrap: stdout contains IRON LAWS"
else
  fail "session-start-bootstrap: stdout contains IRON LAWS" "present" "missing"
fi

# Test: no background service text leaks into stdout
# Supervisor/service output must go to logs, never to stdout
if echo "$SSB_STDOUT" | grep -qi "supervisor"; then
  fail "session-start-bootstrap: no supervisor text in stdout" "absent" "found supervisor text"
else
  pass "session-start-bootstrap: no supervisor text in stdout"
fi

if echo "$SSB_STDOUT" | grep -qi "daemon"; then
  fail "session-start-bootstrap: no daemon text in stdout" "absent" "found daemon text"
else
  pass "session-start-bootstrap: no daemon text in stdout"
fi

if echo "$SSB_STDOUT" | grep -qi "background"; then
  fail "session-start-bootstrap: no background service text in stdout" "absent" "found background text"
else
  pass "session-start-bootstrap: no background service text in stdout"
fi

# Test: logs directory is created (or already exists) after running the hook
if [[ -d "$HOME/.claude/automation/logs" ]]; then
  pass "session-start-bootstrap: automation/logs directory exists after run"
else
  fail "session-start-bootstrap: automation/logs directory exists after run" "directory exists" "not found"
fi

# Test: the script contains the background services section (structural check)
if grep -q "Background services" "$HOOKS_DIR/session-start-bootstrap.sh"; then
  pass "session-start-bootstrap: contains background services section"
else
  fail "session-start-bootstrap: contains background services section" "present" "missing"
fi

# Test: the script references SUPERVISOR_PID for idempotent startup
if grep -q "SUPERVISOR_PID" "$HOOKS_DIR/session-start-bootstrap.sh"; then
  pass "session-start-bootstrap: references SUPERVISOR_PID for idempotent check"
else
  fail "session-start-bootstrap: references SUPERVISOR_PID for idempotent check" "present" "missing"
fi

# Test: the script uses nohup+disown for detached startup (may be on adjacent lines)
if grep -q "nohup" "$HOOKS_DIR/session-start-bootstrap.sh" && grep -q "disown" "$HOOKS_DIR/session-start-bootstrap.sh"; then
  pass "session-start-bootstrap: uses nohup+disown for detached startup"
else
  fail "session-start-bootstrap: uses nohup+disown for detached startup" "present" "missing"
fi

# Test: auto-registration section exists
if grep -q "auto-register\|automation\.env" "$HOOKS_DIR/session-start-bootstrap.sh"; then
  pass "session-start-bootstrap: contains auto-register section"
else
  fail "session-start-bootstrap: contains auto-register section" "present" "missing"
fi

echo ""

# -- Summary -----------------------------------------------------------------
echo "=== Results: $PASS passed, $FAIL failed ==="
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo "Some tests failed. Review hook implementations."
  exit 1
fi

echo "All tests passed."
exit 0

#!/usr/bin/env bats
# Slice 3 — runtime-guard.sh + subagent-stop-trajectory cleanup.
# T3.1-T3.14 covering AC3.1-AC3.12.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/runtime-guard.sh"
  STOP_HOOK="$REPO_ROOT/hooks/subagent-stop-trajectory.sh"
  TMP="$(mktemp -d -t rg.XXXXXX)"
  export CLAUDE_SESSION_ID="rg-test-$$"
  export HOME="$TMP"
  mkdir -p "$TMP/.claude" "$TMP/.claude/pipeline-state"
  unset CLAUDE_SUBAGENT_MAX_RUNTIME CLAUDE_TEAMMATE_MAX_RUNTIME CLAUDE_HOOK_PROFILE
  unset CLAUDE_PIPELINE_TASK_ID CLAUDE_SUBAGENT_ID
  RUNTIME_DIR="$TMP/.claude/metrics/rg-test-$$/subagent-runtimes"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_make_start() {
  # _make_start <key> <ago_seconds> <class> <display>
  mkdir -p "$RUNTIME_DIR"
  local now ts
  now=$(date +%s); ts=$((now - $2))
  printf '%s:%s:%s\n' "$ts" "$3" "$4" > "$RUNTIME_DIR/$1.start"
}

@test "T3.1 Agent invocation writes start file with class=subagent + display" {
  local input='{"tool_name":"Agent","tool_input":{"subagent_type":"software-engineer"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ "$(ls -1 "$RUNTIME_DIR" | wc -l | tr -d ' ')" = "1" ]
  local f; f="$(ls "$RUNTIME_DIR"/*.start | head -1)"
  grep -q ':subagent:software-engineer$' "$f"
}

@test "T3.2 Agent with team_name writes class=teammate + display=name" {
  local input='{"tool_name":"Agent","tool_input":{"subagent_type":"software-engineer","name":"build-engineer","team_name":"pipeline-x"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  local f; f="$(ls "$RUNTIME_DIR"/*.start | head -1)"
  grep -q ':teammate:build-engineer$' "$f"
}

@test "T3.3 Re-invocation on same key does NOT overwrite timestamp" {
  local input='{"tool_name":"Agent","tool_input":{"subagent_type":"software-engineer"}}'
  bash -c "echo '$input' | bash $HOOK" >/dev/null
  local f; f="$(ls "$RUNTIME_DIR"/*.start | head -1)"
  local ts1; ts1="$(cut -d: -f1 "$f")"
  sleep 1
  bash -c "echo '$input' | bash $HOOK" >/dev/null
  local ts2; ts2="$(cut -d: -f1 "$f")"
  [ "$ts1" = "$ts2" ]
}

@test "T3.4 Bash w/ ONE start file, elapsed=1801s, cap=1800 → exit 2 + subagent block msg" {
  _make_start "key1" 1801 "subagent" "se-test"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 2 ]
  echo "$output" | grep -qE "(next tool call blocked|subagent runtime cap)"
  local log="$TMP/.claude/metrics/rg-test-$$/runtime-violations.jsonl"
  [ -f "$log" ]
  grep -q '"record_type":"runtime_violation"' "$log"
  grep -q '"class":"subagent"' "$log"
}

@test "T3.5 Bash w/ ONE start file, elapsed=1799s, cap=1800 → exit 0" {
  _make_start "key1" 1799 "subagent" "se-test"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T3.6 Teammate elapsed=2000s (over sub-cap, under team-cap) → exit 0" {
  _make_start "key2" 2000 "teammate" "tm-test"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T3.7 Teammate over team-cap (3601s) → exit 2 + SendMessage form" {
  _make_start "key3" 3601 "teammate" "tm-display"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q 'SendMessage'
  echo "$output" | grep -q 'shutdown_request'
  echo "$output" | grep -q 'tm-display'
}

@test "T3.8 CLAUDE_SUBAGENT_MAX_RUNTIME=60, elapsed=61 → exit 2 (env override)" {
  _make_start "key4" 61 "subagent" "se-test"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  CLAUDE_SUBAGENT_MAX_RUNTIME=60 run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 2 ]
}

@test "T3.9 Empty start-files dir → exit 0 (graceful)" {
  mkdir -p "$RUNTIME_DIR"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T3.9b No start-files dir at all → exit 0 (cold cache)" {
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T3.10 CLAUDE_HOOK_PROFILE=minimal → bypassed, exit 0" {
  _make_start "key5" 9999 "subagent" "se-test"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  CLAUDE_HOOK_PROFILE=minimal run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T3.11 chain composition with main-branch-guard (separate stdin)" {
  # Two PreToolUse Bash hooks invoked in sequence; each gets its own stdin.
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "echo '$input' | bash $REPO_ROOT/hooks/main-branch-guard.sh"
  [ "$status" -eq 0 ]
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T3.12 SubagentStop cleanup removes start file" {
  # First record a start file via Agent invocation
  local agent_input='{"tool_name":"Agent","tool_input":{"subagent_type":"software-engineer"}}'
  bash -c "echo '$agent_input' | bash $HOOK" >/dev/null
  [ "$(ls "$RUNTIME_DIR"/*.start 2>/dev/null | wc -l | tr -d ' ')" = "1" ]
  # Need a pipeline-state file with verdict: in_progress for the stop hook to record
  local task_id="rg-stop-test"
  cat > "$TMP/.claude/pipeline-state/${task_id}-pipeline.md" <<EOF
---
task_id: $task_id
verdict: in_progress
---
EOF
  CLAUDE_PIPELINE_TASK_ID="$task_id"
  # SubagentStop event JSON — same key derivation (no name/team_name)
  local stop_input='{"subagent_type":"software-engineer"}'
  run bash -c "echo '$stop_input' | CLAUDE_PIPELINE_TASK_ID=$task_id bash $STOP_HOOK"
  [ "$status" -eq 0 ]
  # Start file should now be absent
  [ "$(ls "$RUNTIME_DIR"/*.start 2>/dev/null | wc -l | tr -d ' ')" = "0" ]
}

@test "T3.13 Multiple start files: over-cap one identified by display" {
  _make_start "k1-under" 100 "subagent" "young-agent"
  _make_start "k2-over" 1801 "subagent" "old-agent"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "old-agent"
}

@test "T3.14 No CLAUDE_SUBAGENT_ID dependency (Option C)" {
  unset CLAUDE_SUBAGENT_ID
  _make_start "key-no-env" 1801 "subagent" "se-no-env"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "se-no-env"
}

@test "T3.15 hook + libs ≤50 LOC each" {
  for f in "$REPO_ROOT/hooks/runtime-guard.sh" \
           "$REPO_ROOT/hooks/_lib/runtime-guard-record.sh" \
           "$REPO_ROOT/hooks/_lib/runtime-guard-check.sh" \
           "$REPO_ROOT/hooks/_lib/runtime-guard-key.sh"; do
    local n; n=$(wc -l < "$f")
    [ "$n" -le 50 ] || { echo "FAIL: $f has $n lines"; false; }
  done
}

@test "T3.16 Agent matcher records on Agent tool_name" {
  # Slice 3 also fires on Agent — Mode A. Verify dispatch by tool_name.
  local input='{"tool_name":"Agent","tool_input":{"subagent_type":"se"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ -d "$RUNTIME_DIR" ]
  [ "$(ls "$RUNTIME_DIR"/*.start 2>/dev/null | wc -l | tr -d ' ')" = "1" ]
}

@test "T3.17 Write tool_name triggers scan, not record" {
  _make_start "kw" 1801 "subagent" "wt-test"
  local input='{"tool_name":"Write","tool_input":{"file_path":"/tmp/x"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 2 ]
}

@test "T3.18 Edit tool_name triggers scan" {
  _make_start "ke" 1801 "subagent" "ed-test"
  local input='{"tool_name":"Edit","tool_input":{"file_path":"/tmp/x"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 2 ]
}

@test "T3.19 Read tool_name short-circuits exit 0 (Read excluded per AC3.1)" {
  _make_start "kr" 9999 "subagent" "rd-test"
  local input='{"tool_name":"Read","tool_input":{"file_path":"/tmp/x"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
}

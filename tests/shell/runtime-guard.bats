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
  # Exactly one .start file (the hook also writes a sibling .count file, so
  # count .start specifically rather than all directory entries).
  [ "$(ls -1 "$RUNTIME_DIR"/*.start | wc -l | tr -d ' ')" = "1" ]
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
           "$REPO_ROOT/hooks/_lib/runtime-guard-emit.sh" \
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

@test "T3.20 SubagentStop cleanup removes teammate start file (HIGH #1 regression)" {
  # Spawn a TEAMMATE (with name + team_name set) — represents the most common
  # dispatch class. The bug: SubagentStop payload does NOT reliably expose
  # tool_input.name / tool_input.team_name, so cleanup-side computed a different
  # key and the .start file leaked.
  local agent_input='{"tool_name":"Agent","tool_input":{"subagent_type":"software-engineer","name":"build-engineer","team_name":"pipeline-x"}}'
  bash -c "echo '$agent_input' | bash $HOOK" >/dev/null
  [ "$(ls "$RUNTIME_DIR"/*.start 2>/dev/null | wc -l | tr -d ' ')" = "1" ]
  local task_id="rg-stop-tm"
  cat > "$TMP/.claude/pipeline-state/${task_id}-pipeline.md" <<EOF
---
task_id: $task_id
verdict: in_progress
---
EOF
  # SubagentStop event — note: no tool_input wrapper, fields at top level
  # (mirrors what subagent-stop-trajectory.sh actually receives).
  local stop_input='{"subagent_type":"software-engineer","subagent_id":"sa-123"}'
  run bash -c "echo '$stop_input' | CLAUDE_PIPELINE_TASK_ID=$task_id bash $STOP_HOOK"
  [ "$status" -eq 0 ]
  [ "$(ls "$RUNTIME_DIR"/*.start 2>/dev/null | wc -l | tr -d ' ')" = "0" ]
}

@test "T3.21 _rg_compute_key requires only subagent_type (per-class semantic)" {
  # Document the per-class trade-off: the key is derived from subagent_type ONLY,
  # so spawn and SubagentStop always agree even when SubagentStop omits name/team.
  source "$REPO_ROOT/hooks/_lib/runtime-guard-key.sh"
  local k1 k2
  k1=$(_rg_compute_key "software-engineer" "" "")
  k2=$(_rg_compute_key "software-engineer" "build-engineer" "pipeline-x")
  [ -n "$k1" ]
  [ "$k1" = "$k2" ]
}

@test "T3.22 _rg_compute_key falls back to 'unknown' when no hasher available" {
  source "$REPO_ROOT/hooks/_lib/runtime-guard-key.sh"
  local key
  # Restrict PATH to just the bats/coreutils minimum, excluding sha1sum and shasum.
  key=$(PATH="/var/empty" _rg_compute_key "software-engineer" "" "")
  [ "$key" = "unknown" ]
}

@test "T3.23 runtime-violations.jsonl includes task_id (R2 product finding #4)" {
  _make_start "key-tid" 1801 "subagent" "tid-test"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  CLAUDE_PIPELINE_TASK_ID="task-runtime-x" run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 2 ]
  local log="$TMP/.claude/metrics/rg-test-$$/runtime-violations.jsonl"
  [ -f "$log" ]
  grep -q '"task_id":"task-runtime-x"' "$log"
  grep -q '"agent_key":' "$log"
  grep -q '"display_name":"tid-test"' "$log"
  grep -q '"elapsed_seconds":' "$log"
  grep -q '"cap_seconds":' "$log"
  grep -q '"action":"shutdown_signaled"' "$log"
  grep -q '"timestamp":' "$log"
  grep -q '"session_id":' "$log"
}

@test "T3.24 malformed .start file (non-numeric ts) is silently skipped" {
  # Edge: an over-cap good file alongside a malformed file → only good triggers.
  mkdir -p "$RUNTIME_DIR"
  printf 'abc:subagent:malformed\n' > "$RUNTIME_DIR/bad.start"
  printf 'no-colons-at-all\n' > "$RUNTIME_DIR/worse.start"
  local input='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  # Now add an over-cap valid file — the malformed ones must not block detection.
  _make_start "good" 1801 "subagent" "good-agent"
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "good-agent"
  echo "$output" | grep -qv "malformed"
}

@test "T3.25 SubagentStop cleanup is idempotent when start file absent" {
  # Pipeline state file required for the trajectory writer to proceed.
  local task_id="rg-idemp"
  mkdir -p "$TMP/.claude/pipeline-state"
  printf -- '---\ntask_id: %s\nverdict: in_progress\n---\n' "$task_id" \
    > "$TMP/.claude/pipeline-state/${task_id}-pipeline.md"
  # No start file present — cleanup must not error.
  local stop_input='{"subagent_type":"software-engineer","subagent_id":"sa-idemp"}'
  run bash -c "echo '$stop_input' | CLAUDE_PIPELINE_TASK_ID=$task_id bash $STOP_HOOK"
  [ "$status" -eq 0 ]
  # Re-running cleanup is also a no-op.
  run bash -c "echo '$stop_input' | CLAUDE_PIPELINE_TASK_ID=$task_id bash $STOP_HOOK"
  [ "$status" -eq 0 ]
}

@test "T3.26 empty CLAUDE_SESSION_ID writes to local-\$pid runtime path" {
  # Empty SID must produce a 'local-<pid>' path segment, never '//'.
  # Mode A: spawn an Agent with empty SID and assert the start file lands
  # under metrics/local-*/subagent-runtimes/, not under metrics//.
  local input='{"tool_name":"Agent","tool_input":{"subagent_type":"se-empty-sid"}}'
  CLAUDE_SESSION_ID="" run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  # Critical invariant: no double-slash directory was created.
  [ ! -d "$TMP/.claude/metrics//subagent-runtimes" ]
  # And SOME local-* directory exists with one start file.
  local count
  count=$(ls -1 "$TMP/.claude/metrics/local-"*/subagent-runtimes/*.start 2>/dev/null | wc -l | tr -d ' ')
  [ "$count" -ge 1 ]
}

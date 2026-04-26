#!/usr/bin/env bats
# Slice 2 — depth-guard.sh (PreToolUse Agent).
# T2.1-T2.9 covering AC2.1-AC2.9.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/depth-guard.sh"
  TMP="$(mktemp -d -t dg.XXXXXX)"
  export CLAUDE_SESSION_ID="dg-test-$$"
  export HOME="$TMP"  # redirect metrics writes
  mkdir -p "$TMP/.claude"
  unset CLAUDE_SUBAGENT_DEPTH CLAUDE_SUBAGENT_MAX_DEPTH CLAUDE_HOOK_PROFILE
  unset CLAUDE_PIPELINE_TASK_ID
  AGENT_INPUT='{"tool_name":"Agent","tool_input":{"subagent_type":"software-engineer"}}'
  NON_AGENT_INPUT='{"tool_name":"Bash","tool_input":{"command":"echo hi"}}'
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

@test "T2.1 depth unset → exit 0 (top-level orchestrator allowed)" {
  run bash -c "echo '$AGENT_INPUT' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T2.2 depth=2, max=3 → exit 0 (below cap)" {
  CLAUDE_SUBAGENT_DEPTH=2 run bash -c "echo '$AGENT_INPUT' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T2.3 depth=3, max=3 → exit 2 with refusal stderr" {
  CLAUDE_SUBAGENT_DEPTH=3 run bash -c "echo '$AGENT_INPUT' | bash $HOOK"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "max recursion depth" || echo "$output" | grep -q "BLOCKED"
}

@test "T2.4 depth=4, max=3 → exit 2" {
  CLAUDE_SUBAGENT_DEPTH=4 run bash -c "echo '$AGENT_INPUT' | bash $HOOK"
  [ "$status" -eq 2 ]
}

@test "T2.5 CLAUDE_SUBAGENT_MAX_DEPTH=5 raises cap, depth=4 → exit 0" {
  CLAUDE_SUBAGENT_DEPTH=4 CLAUDE_SUBAGENT_MAX_DEPTH=5 run bash -c "echo '$AGENT_INPUT' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T2.6 CLAUDE_SUBAGENT_MAX_DEPTH=2 lowers cap, depth=2 → exit 2" {
  CLAUDE_SUBAGENT_DEPTH=2 CLAUDE_SUBAGENT_MAX_DEPTH=2 run bash -c "echo '$AGENT_INPUT' | bash $HOOK"
  [ "$status" -eq 2 ]
}

@test "T2.7 violation logged with required fields" {
  CLAUDE_SUBAGENT_DEPTH=3 CLAUDE_PIPELINE_TASK_ID="task-x" run bash -c "echo '$AGENT_INPUT' | bash $HOOK"
  local log="$TMP/.claude/metrics/dg-test-$$/depth-violations.jsonl"
  [ -f "$log" ]
  grep -q '"record_type":"depth_violation"' "$log"
  grep -q '"depth":3' "$log"
  grep -q '"max_depth":3' "$log"
  grep -q '"subagent_type":"software-engineer"' "$log"
  grep -q '"task_id":"task-x"' "$log"
  grep -q '"action":"prevented"' "$log"
}

@test "T2.8 CLAUDE_HOOK_PROFILE=minimal → bypassed, exit 0" {
  CLAUDE_SUBAGENT_DEPTH=3 CLAUDE_HOOK_PROFILE=minimal run bash -c "echo '$AGENT_INPUT' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T2.9 non-Agent tool_name → short-circuit exit 0" {
  CLAUDE_SUBAGENT_DEPTH=10 run bash -c "echo '$NON_AGENT_INPUT' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "T2.10 hook file ≤50 LOC" {
  local n; n=$(wc -l < "$HOOK")
  [ "$n" -le 50 ]
}

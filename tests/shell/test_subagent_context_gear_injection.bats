#!/usr/bin/env bats
# Phase B — hooks/subagent-context.sh gear-aware additionalContext injection.
#
# SubagentStart's hookSpecificOutput.additionalContext lets this hook inject
# rules content directly into the SPAWNING subagent's own context. safety.md
# content is ALWAYS included (every gear); pipeline-rigour.md content is
# included ONLY when gear != PAIR (BUILD, PIPELINE, or gear-absent — fail
# toward MORE rules, never fewer).
#
# Run from repo root (worktree cwd produces false-reds for cwd-sensitive
# guards elsewhere in this suite — this test is hermetic to CLAUDE_STATE_DIR
# so it is not itself cwd-sensitive, but the convention is followed anyway).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/subagent-context.sh"
  TMP_STATE="$(mktemp -d)"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_STATE_DIR="$TMP_STATE/state"
  mkdir -p "$CLAUDE_STATE_DIR"
}

teardown() {
  rm -rf "$TMP_STATE"
}

_write_gear() {
  local sid="$1" gear="$2"
  printf '%s\n' "$gear" > "$CLAUDE_STATE_DIR/gear-${sid}"
}

_spawn_json() {
  local agent_type="$1" sid="$2"
  printf '{"subagent_type":"%s","session_id":"%s"}' "$agent_type" "$sid"
}

@test "PAIR gear: additionalContext contains safety markers, omits pipeline-rigour markers" {
  _write_gear "sid-pair-1" "PAIR"
  run bash -c "printf '%s' '$(_spawn_json software-engineer sid-pair-1)' | CLAUDE_PLUGIN_ROOT='$CLAUDE_PLUGIN_ROOT' CLAUDE_STATE_DIR='$CLAUDE_STATE_DIR' bash '$HOOK'"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "hookSpecificOutput"
  additional_context=$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')
  echo "$additional_context" | grep -qi "orchestrator never writes"
  ! echo "$additional_context" | grep -qi "mutation score"
  ! echo "$additional_context" | grep -q "NO PHASE SKIPPED"
}

@test "BUILD gear: additionalContext contains BOTH safety and pipeline-rigour markers" {
  _write_gear "sid-build-1" "BUILD"
  run bash -c "printf '%s' '$(_spawn_json software-engineer sid-build-1)' | CLAUDE_PLUGIN_ROOT='$CLAUDE_PLUGIN_ROOT' CLAUDE_STATE_DIR='$CLAUDE_STATE_DIR' bash '$HOOK'"
  [ "$status" -eq 0 ]
  additional_context=$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')
  echo "$additional_context" | grep -qi "orchestrator never writes"
  echo "$additional_context" | grep -qi "mutation score"
  echo "$additional_context" | grep -q "NO PHASE SKIPPED"
}

@test "PIPELINE gear: additionalContext contains BOTH safety and pipeline-rigour markers" {
  _write_gear "sid-pipeline-1" "PIPELINE"
  run bash -c "printf '%s' '$(_spawn_json software-engineer sid-pipeline-1)' | CLAUDE_PLUGIN_ROOT='$CLAUDE_PLUGIN_ROOT' CLAUDE_STATE_DIR='$CLAUDE_STATE_DIR' bash '$HOOK'"
  [ "$status" -eq 0 ]
  additional_context=$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')
  echo "$additional_context" | grep -qi "orchestrator never writes"
  echo "$additional_context" | grep -qi "mutation score"
}

@test "absent gear state: fails toward MORE rules (BOTH safety and pipeline-rigour present)" {
  # No _write_gear call: gear-${sid} key never written.
  run bash -c "printf '%s' '$(_spawn_json software-engineer sid-absent-1)' | CLAUDE_PLUGIN_ROOT='$CLAUDE_PLUGIN_ROOT' CLAUDE_STATE_DIR='$CLAUDE_STATE_DIR' bash '$HOOK'"
  [ "$status" -eq 0 ]
  additional_context=$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')
  echo "$additional_context" | grep -qi "orchestrator never writes"
  echo "$additional_context" | grep -qi "mutation score"
}

@test "agent-role state write still happens (observation-capture.sh dependency preserved)" {
  _write_gear "sid-role-1" "BUILD"
  bash -c "printf '%s' '$(_spawn_json qa-engineer sid-role-1)' | CLAUDE_PLUGIN_ROOT='$CLAUDE_PLUGIN_ROOT' CLAUDE_STATE_DIR='$CLAUDE_STATE_DIR' bash '$HOOK'" >/dev/null
  role_files=$(find "$CLAUDE_STATE_DIR" -name 'agent-role-*' -type f)
  [ -n "$role_files" ]
  grep -q "qa-engineer" $role_files
}

@test "empty stdin: unevaluable input still emits safety-only context, exits 0 (fail toward safety, not crash)" {
  run bash -c "printf '' | CLAUDE_PLUGIN_ROOT='$CLAUDE_PLUGIN_ROOT' CLAUDE_STATE_DIR='$CLAUDE_STATE_DIR' bash '$HOOK'"
  [ "$status" -eq 0 ]
}

@test "output is valid JSON parseable by jq" {
  _write_gear "sid-json-1" "PAIR"
  run bash -c "printf '%s' '$(_spawn_json software-engineer sid-json-1)' | CLAUDE_PLUGIN_ROOT='$CLAUDE_PLUGIN_ROOT' CLAUDE_STATE_DIR='$CLAUDE_STATE_DIR' bash '$HOOK'"
  [ "$status" -eq 0 ]
  echo "$output" | jq . >/dev/null
}

@test "hookEventName is SubagentStart" {
  _write_gear "sid-event-1" "PAIR"
  run bash -c "printf '%s' '$(_spawn_json software-engineer sid-event-1)' | CLAUDE_PLUGIN_ROOT='$CLAUDE_PLUGIN_ROOT' CLAUDE_STATE_DIR='$CLAUDE_STATE_DIR' bash '$HOOK'"
  [ "$status" -eq 0 ]
  event=$(echo "$output" | jq -r '.hookSpecificOutput.hookEventName')
  [ "$event" = "SubagentStart" ]
}

@test "runs under minimal hook profile too (rules injection is not gated behind check_hook_profile standard)" {
  _write_gear "sid-minimal-1" "BUILD"
  run bash -c "printf '%s' '$(_spawn_json software-engineer sid-minimal-1)' | CLAUDE_PLUGIN_ROOT='$CLAUDE_PLUGIN_ROOT' CLAUDE_STATE_DIR='$CLAUDE_STATE_DIR' CLAUDE_HOOK_PROFILE=minimal bash '$HOOK'"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q "hookSpecificOutput"
  additional_context=$(echo "$output" | jq -r '.hookSpecificOutput.additionalContext')
  echo "$additional_context" | grep -qi "orchestrator never writes"
}

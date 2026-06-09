#!/usr/bin/env bats
# GP-P1-01 — agent-injection capability probe.
#
# Slice A (A1-A3): unit-tests hooks/_lib/agent-injection-capability.sh's pure
# function agent_injection_supported (default 1 = unsupported; 0 iff
# CLAUDE_AGENT_INJECTION_FORCE=1; no stdout, no exit).
#
# Slice B (B1-B7): integration — the three PreToolUse:Agent resolver hooks
# (pre-agent-thinking, pre-agent-advisor, cache-breakpoint-injector) skip their
# python resolver (no resolver-jsonl line) by default, restore it under FORCE=1,
# and ALWAYS preserve hooks.jsonl subagent_type on the default short-circuit
# path (proves the probe sits BELOW the SUBAGENT_TYPE parse — the hoist).
#
# CI globs tests/shell/*.bats only — this file MUST live here.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HELPER="$REPO_ROOT/hooks/_lib/agent-injection-capability.sh"
  THINKING_HOOK="$REPO_ROOT/hooks/pre-agent-thinking.sh"
  ADVISOR_HOOK="$REPO_ROOT/hooks/pre-agent-advisor.sh"
  CACHE_HOOK="$REPO_ROOT/hooks/cache-breakpoint-injector.sh"
  TMP="$(mktemp -d -t aicap.XXXXXX)"
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"
  export CLAUDE_PLUGIN_DATA="$TMP/.claude"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="aicap-test-$$"
  unset CLAUDE_HOOK_PROFILE
  unset CLAUDE_AGENT_INJECTION_FORCE
  SESSION_DIR="$CLAUDE_PLUGIN_DATA/metrics/$CLAUDE_SESSION_ID"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_agent_envelope() {
  printf '{"tool_name":"Agent","tool_input":{"subagent_type":"software-engineer","prompt":"build slice"}}'
}

# ---------------------------------------------------------------------------
# Slice A — helper unit (A1-A3)
# ---------------------------------------------------------------------------

@test "A1: agent_injection_supported returns 1 (unsupported) by default" {
  run bash -c "unset CLAUDE_AGENT_INJECTION_FORCE; source '$HELPER'; agent_injection_supported"
  [ "$status" -eq 1 ]
}

@test "A2: agent_injection_supported returns 0 when CLAUDE_AGENT_INJECTION_FORCE=1" {
  run bash -c "export CLAUDE_AGENT_INJECTION_FORCE=1; source '$HELPER'; agent_injection_supported"
  [ "$status" -eq 0 ]
}

@test "A3: agent_injection_supported is pure (no stdout, survives sourcing)" {
  # Capture stdout only; assert empty AND the sourcing shell reaches the marker
  # (proves the function does not call exit on either branch).
  run bash -c "source '$HELPER'; agent_injection_supported; echo MARKER"
  [ "$status" -eq 0 ]
  [ "$output" = "MARKER" ]
}

# ---------------------------------------------------------------------------
# Slice B — integration (B1-B7)
# ---------------------------------------------------------------------------

@test "B1: pre-agent-thinking default → no hook-injections.jsonl, exit 0" {
  run bash -c "echo '$(_agent_envelope)' | bash '$THINKING_HOOK'"
  [ "$status" -eq 0 ]
  [ ! -f "$SESSION_DIR/hook-injections.jsonl" ]
}

@test "B2: pre-agent-advisor default → no advisor-dispatch.jsonl, exit 0" {
  run bash -c "echo '$(_agent_envelope)' | bash '$ADVISOR_HOOK'"
  [ "$status" -eq 0 ]
  [ ! -f "$SESSION_DIR/advisor-dispatch.jsonl" ]
}

@test "B3: cache-breakpoint-injector default → no cache-injections.jsonl, exit 0" {
  run bash -c "echo '$(_agent_envelope)' | bash '$CACHE_HOOK'"
  [ "$status" -eq 0 ]
  [ ! -f "$SESSION_DIR/cache-injections.jsonl" ]
}

@test "B4: FORCE=1 → thinking resolver LOG line IS written" {
  run bash -c "export CLAUDE_AGENT_INJECTION_FORCE=1; echo '$(_agent_envelope)' | bash '$THINKING_HOOK'"
  [ "$status" -eq 0 ]
  [ -f "$SESSION_DIR/hook-injections.jsonl" ]
  [ "$(wc -l < "$SESSION_DIR/hook-injections.jsonl" | tr -d ' ')" = "1" ]
}

@test "B5: FORCE=1 → advisor + cache resolver LOG lines ARE written" {
  run bash -c "export CLAUDE_AGENT_INJECTION_FORCE=1; echo '$(_agent_envelope)' | bash '$ADVISOR_HOOK'"
  [ "$status" -eq 0 ]
  [ -f "$SESSION_DIR/advisor-dispatch.jsonl" ]
  run bash -c "export CLAUDE_AGENT_INJECTION_FORCE=1; echo '$(_agent_envelope)' | bash '$CACHE_HOOK'"
  [ "$status" -eq 0 ]
  [ -f "$SESSION_DIR/cache-injections.jsonl" ]
}

@test "B6: default short-circuit STILL writes hooks.jsonl carrying subagent_type" {
  run bash -c "echo '$(_agent_envelope)' | bash '$THINKING_HOOK'"
  [ "$status" -eq 0 ]
  [ -f "$SESSION_DIR/hooks.jsonl" ]
  local last; last="$(tail -n 1 "$SESSION_DIR/hooks.jsonl")"
  echo "$last" | grep -q '"subagent_type":"software-engineer"'
}

@test "B7: cache hook body still ≤35 lines after probe insert" {
  local n; n=$(wc -l < "$CACHE_HOOK" | tr -d ' ')
  [ "$n" -le 35 ]
}

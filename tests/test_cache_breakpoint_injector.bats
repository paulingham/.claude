#!/usr/bin/env bats
# Slice B — hooks/cache-breakpoint-injector.sh PreToolUse:Agent advisory hook.
# Path-B advisory shape mirroring hooks/pre-agent-thinking.sh exactly.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  HOOK="$REPO_ROOT/hooks/cache-breakpoint-injector.sh"
  TMP="$(mktemp -d -t cbi.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="cbi-test-$$"
  mkdir -p "$TMP/.claude/metrics" "$TMP/.claude/rules"
  # Mirror real rules/core.md byte-for-byte for hash-stability fixture coverage.
  cp "$REPO_ROOT/rules/core.md" "$TMP/.claude/rules/core.md"
  LOG_DIR="$TMP/.claude/metrics/$CLAUDE_SESSION_ID"
  LOG="$LOG_DIR/cache-injections.jsonl"
  unset CLAUDE_HOOK_PROFILE
  # GP-P1-01: resolvers short-circuit by default; force the python path so the
  # record-emitting test still exercises it. minimal-profile / non-Agent tests
  # short-circuit before the probe so this export does not affect them.
  export CLAUDE_AGENT_INJECTION_FORCE=1
  export CLAUDE_CONFIG_DIR="$TMP/.claude"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_agent_envelope() {
  printf '{"tool_name":"Agent","tool_input":{"subagent_type":"software-engineer","prompt":"build slice"}}'
}

@test "cache-breakpoint-injector.sh exits 0 on empty stdin AND is executable" {
  [ -f "$HOOK" ]
  [ -x "$HOOK" ]
  run bash -c "printf '' | bash $HOOK"
  [ "$status" -eq 0 ]
}

@test "cache-breakpoint-injector.sh logs cache-injections.jsonl record on valid Agent envelope" {
  local input; input="$(_agent_envelope)"
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ -f "$LOG" ]
  [ "$(wc -l < "$LOG" | tr -d ' ')" = "1" ]
  grep -qE '"agent_role":[[:space:]]*"software-engineer"' "$LOG"
  grep -q "rules-core-tail" "$LOG"
  grep -q "persona-marker-deferred" "$LOG"
}

@test "cache-breakpoint-injector.sh no-ops when tool_name is not Agent" {
  local input='{"tool_name":"Skill","tool_input":{"subagent_type":"x"}}'
  run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ ! -f "$LOG" ] || [ "$(wc -l < "$LOG" | tr -d ' ')" = "0" ]
}

@test "cache-breakpoint-injector.sh short-circuits under CLAUDE_HOOK_PROFILE=minimal" {
  local input; input="$(_agent_envelope)"
  CLAUDE_HOOK_PROFILE=minimal run bash -c "echo '$input' | bash $HOOK"
  [ "$status" -eq 0 ]
  [ ! -f "$LOG" ] || [ "$(wc -l < "$LOG" | tr -d ' ')" = "0" ]
}

@test "cache-breakpoint-injector.sh body ≤35 lines" {
  local n; n=$(wc -l < "$HOOK" | tr -d ' ')
  [ "$n" -le 35 ]
}

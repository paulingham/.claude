#!/usr/bin/env bats
# AC11 / AC7 — spec-blind-validator write-guard.
# Verifies:
#   - Writes under tests/, test/, spec/, __tests__/ are allowed
#   - Writes to src/** denied (exit 2 + JSONL)
#   - Writes to package.json denied (read-only manifest)
#   - Other subagent_type fast-exits 0

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/spec-blind-write-guard.sh"
  TMP="$(mktemp -d -t sbw.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="sbw-test-$$"
  export CLAUDE_CONFIG_DIR="$REPO_ROOT"
  export CLAUDE_HOOK_PROFILE="minimal"
  mkdir -p "$TMP/.claude"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_run_hook() {
  local subagent="$1" tool="$2" path="$3"
  local payload
  payload=$(jq -nc --arg s "$subagent" --arg t "$tool" --arg p "$path" --arg sid "$CLAUDE_SESSION_ID" \
    '{tool_name:$t, subagent_type:$s, tool_input:{file_path:$p}, session_id:$sid}')
  echo "$payload" | bash "$HOOK"
}

@test "SBW1 write under tests/ is allowed" {
  run _run_hook "spec-blind-validator" "Write" "/tmp/proj/tests/spec_blind_authored.test.ts"
  [ "$status" -eq 0 ]
}

@test "SBW2 write under spec/ is allowed" {
  run _run_hook "spec-blind-validator" "Write" "/tmp/proj/spec/users_spec.rb"
  [ "$status" -eq 0 ]
}

@test "SBW3 write under __tests__/ is allowed" {
  run _run_hook "spec-blind-validator" "Write" "/tmp/proj/src/foo/__tests__/foo.test.ts"
  [ "$status" -eq 0 ]
}

@test "SBW4 write to src/auth.ts is denied (exit 2 + JSONL)" {
  run _run_hook "spec-blind-validator" "Write" "/tmp/proj/src/auth.ts"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "BLOCKED: spec-blind-validator may not write"
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  [ -f "$LOG" ]
  grep -q "spec_blind_blocked" "$LOG"
  grep -q "write-guard" "$LOG"
}

@test "SBW5 write to package.json is denied (read-only manifest)" {
  run _run_hook "spec-blind-validator" "Write" "/tmp/proj/package.json"
  [ "$status" -eq 2 ]
}

@test "SBW6 edit to interface.ts is denied (read-only)" {
  run _run_hook "spec-blind-validator" "Edit" "/tmp/proj/lib/interface.ts"
  [ "$status" -eq 2 ]
}

@test "SBW7 other subagent_type fast-exits 0 even on src write" {
  run _run_hook "software-engineer" "Write" "/tmp/proj/src/auth.ts"
  [ "$status" -eq 0 ]
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  [ ! -f "$LOG" ]
}

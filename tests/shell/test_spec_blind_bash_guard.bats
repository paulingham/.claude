#!/usr/bin/env bats
# AC15-bats — spec-blind-validator bash-guard.
# Verifies the 7-runner ladder is allowed and content-leak shapes (cat/head/
# tail/sed/awk/xxd/hexdump on src, node -e/python -c/ruby -e/perl -e,
# grep -r src/, find src/) are all blocked when subagent_type is
# spec-blind-validator. Other subagents fast-exit 0.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/spec-blind-bash-guard.sh"
  TMP="$(mktemp -d -t sbb.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="sbb-test-$$"
  export CLAUDE_CONFIG_DIR="$REPO_ROOT"
  export CLAUDE_HOOK_PROFILE="minimal"
  mkdir -p "$TMP/.claude"
}

teardown() {
  [ -d "$TMP" ] && rm -rf "$TMP"
}

_run_hook() {
  local subagent="$1" cmd="$2"
  local payload
  payload=$(jq -nc --arg s "$subagent" --arg c "$cmd" --arg sid "$CLAUDE_SESSION_ID" \
    '{tool_name:"Bash", subagent_type:$s, tool_input:{command:$c}, session_id:$sid}')
  echo "$payload" | bash "$HOOK"
}

# --- Allowed: 7-runner ladder ---

@test "SBB-A1 npm test is allowed" {
  run _run_hook "spec-blind-validator" "npm test"
  [ "$status" -eq 0 ]
}

@test "SBB-A2 pytest tests/ is allowed" {
  run _run_hook "spec-blind-validator" "pytest tests/"
  [ "$status" -eq 0 ]
}

@test "SBB-A3 bundle exec rspec spec/ is allowed" {
  run _run_hook "spec-blind-validator" "bundle exec rspec spec/"
  [ "$status" -eq 0 ]
}

@test "SBB-A4 cargo test is allowed" {
  run _run_hook "spec-blind-validator" "cargo test --lib"
  [ "$status" -eq 0 ]
}

@test "SBB-A5 go test ./... is allowed" {
  run _run_hook "spec-blind-validator" "go test ./..."
  [ "$status" -eq 0 ]
}

@test "SBB-A6 pnpm test is allowed" {
  run _run_hook "spec-blind-validator" "pnpm test --watch=false"
  [ "$status" -eq 0 ]
}

@test "SBB-A7 yarn test is allowed" {
  run _run_hook "spec-blind-validator" "yarn test"
  [ "$status" -eq 0 ]
}

# --- Blocked: content-leak shapes ---

@test "SBB-B1 cat src/auth.ts is denied (exit 2 + JSONL)" {
  run _run_hook "spec-blind-validator" "cat src/auth.ts"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "BLOCKED: spec-blind-validator"
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  [ -f "$LOG" ]
  grep -q "spec_blind_blocked" "$LOG"
  grep -q "bash-guard" "$LOG"
}

@test "SBB-B2 node -e require src is denied" {
  run _run_hook "spec-blind-validator" "node -e 'console.log(require(\"./src/x\"))'"
  [ "$status" -eq 2 ]
}

@test "SBB-B3 python -c open src is denied" {
  run _run_hook "spec-blind-validator" "python -c 'print(open(\"src/x.py\").read())'"
  [ "$status" -eq 2 ]
}

@test "SBB-B4 grep -r src/ is denied" {
  run _run_hook "spec-blind-validator" "grep -r 'foo' src/"
  [ "$status" -eq 2 ]
}

@test "SBB-B5 xxd src/x.bin is denied" {
  run _run_hook "spec-blind-validator" "xxd src/x.bin"
  [ "$status" -eq 2 ]
}

@test "SBB-B6 hexdump src/x is denied" {
  run _run_hook "spec-blind-validator" "hexdump src/x"
  [ "$status" -eq 2 ]
}

@test "SBB-B7 ruby -e File.read src is denied" {
  run _run_hook "spec-blind-validator" "ruby -e 'puts File.read(\"src/x.rb\")'"
  [ "$status" -eq 2 ]
}

@test "SBB-B8 perl -e is denied" {
  run _run_hook "spec-blind-validator" "perl -e 'print <>' src/x.pl"
  [ "$status" -eq 2 ]
}

@test "SBB-B9 head src is denied" {
  run _run_hook "spec-blind-validator" "head src/auth.ts"
  [ "$status" -eq 2 ]
}

@test "SBB-B10 find src/ is denied" {
  run _run_hook "spec-blind-validator" "find src/ -name '*.ts'"
  [ "$status" -eq 2 ]
}

# --- Other subagent types fast-exit ---

@test "SBB-C1 other subagent_type running cat src fast-exits 0" {
  run _run_hook "software-engineer" "cat src/auth.ts"
  [ "$status" -eq 0 ]
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  [ ! -f "$LOG" ]
}

@test "SBB-C2 other subagent_type running an arbitrary script fast-exits 0" {
  run _run_hook "qa-engineer" "ls -la"
  [ "$status" -eq 0 ]
}

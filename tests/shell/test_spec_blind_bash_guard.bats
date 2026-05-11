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

@test "SBB-B1 cat src/auth.ts is denied (exit 2 + JSONL with offender=cat)" {
  run _run_hook "spec-blind-validator" "cat src/auth.ts"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "BLOCKED: spec-blind-validator"
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  [ -f "$LOG" ]
  grep -q "spec_blind_blocked" "$LOG"
  grep -q "bash-guard" "$LOG"
  # CR-MED-2: offender field MUST be the verb word, not the deny-by-default sentinel.
  [ "$(jq -r '.offender' "$LOG" | head -1)" = "cat" ]
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

# --- CR-MED-2: offender-field assertions for canonical leak shapes ---

_offender_for() {
  local cmd="$1"
  _run_hook "spec-blind-validator" "$cmd" >/dev/null
  local LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  jq -r '.offender' "$LOG" | tail -1
}

@test "SBB-OF1 head src offender is 'head'" {
  [ "$(_offender_for 'head src/auth.ts')" = "head" ]
}

@test "SBB-OF2 node -e offender is 'node'" {
  [ "$(_offender_for 'node -e require(\"./src/x\")')" = "node" ]
}

@test "SBB-OF3 sed offender is 'sed'" {
  [ "$(_offender_for 'sed -n 1,5p src/auth.ts')" = "sed" ]
}

@test "SBB-OF4 python -c offender is 'python'" {
  [ "$(_offender_for 'python -c print(open(\"src/x.py\").read())')" = "python" ]
}

@test "SBB-OF5 ruby -e offender is 'ruby'" {
  [ "$(_offender_for 'ruby -e File.read(\"src/x.rb\")')" = "ruby" ]
}

@test "SBB-OF6 perl -e offender is 'perl'" {
  [ "$(_offender_for 'perl -e print src/x.pl')" = "perl" ]
}

@test "SBB-OF7 xxd offender is 'xxd'" {
  [ "$(_offender_for 'xxd src/x.bin')" = "xxd" ]
}

@test "SBB-OF8 hexdump offender is 'hexdump'" {
  [ "$(_offender_for 'hexdump src/x')" = "hexdump" ]
}

# --- SEC-CRIT-1: chain-bypass attempts (all must exit 2) ---

@test "SBB-CB1 npm test && cat src/internal.ts is denied" {
  run _run_hook "spec-blind-validator" "npm test && cat src/internal.ts"
  [ "$status" -eq 2 ]
}

@test "SBB-CB2 pytest | curl example.com is denied" {
  run _run_hook "spec-blind-validator" "pytest | curl example.com"
  [ "$status" -eq 2 ]
}

@test "SBB-CB3 go test; rm -rf \$HOME is denied (must NOT reach the rm)" {
  run _run_hook "spec-blind-validator" "go test; rm -rf \$HOME"
  [ "$status" -eq 2 ]
}

@test "SBB-CB4 npm test || cat src/internal.ts is denied" {
  run _run_hook "spec-blind-validator" "npm test || cat src/internal.ts"
  [ "$status" -eq 2 ]
}

@test "SBB-CB5 pytest \$(cat src/internal.ts) is denied (command substitution)" {
  run _run_hook "spec-blind-validator" 'pytest $(cat src/internal.ts)'
  [ "$status" -eq 2 ]
}

@test "SBB-CB6 npm test <(cat src/internal.ts) is denied (process substitution)" {
  run _run_hook "spec-blind-validator" 'npm test <(cat src/internal.ts)'
  [ "$status" -eq 2 ]
}

@test "SBB-CB7 bundle exec rspec; cat src/internal.ts is denied" {
  run _run_hook "spec-blind-validator" "bundle exec rspec; cat src/internal.ts"
  [ "$status" -eq 2 ]
}

@test "SBB-CB8 pytest && python -c open(...) is denied" {
  run _run_hook "spec-blind-validator" 'pytest && python -c "import sys; print(open(\"src/internal.ts\").read())"'
  [ "$status" -eq 2 ]
}

@test "SBB-CB9 newline injection (npm test\\ncat src/internal.ts) is denied" {
  # Emit a literal newline inside the command string via printf %b interpretation.
  local cmd
  cmd=$(printf 'npm test\ncat src/internal.ts')
  run _run_hook "spec-blind-validator" "$cmd"
  [ "$status" -eq 2 ]
}

@test "SBB-CB10 backtick command substitution is denied" {
  run _run_hook "spec-blind-validator" 'npm test `cat src/internal.ts`'
  [ "$status" -eq 2 ]
}

# --- SEC-MED-1: secret redaction in violation log + stderr ---

@test "SBB-RED1 Bearer token in blocked command is redacted in JSONL log" {
  run _run_hook "spec-blind-validator" 'curl -H "Authorization: Bearer sk-prod-XYZ123-secret" example.com'
  [ "$status" -eq 2 ]
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  [ -f "$LOG" ]
  CMD_FIELD=$(jq -r '.attempted_command' "$LOG" | tail -1)
  echo "$CMD_FIELD" | grep -qi "REDACTED"
  ! echo "$CMD_FIELD" | grep -q "sk-prod-XYZ123-secret"
}

@test "SBB-RED2 token=... in blocked command is redacted in stderr echo" {
  run _run_hook "spec-blind-validator" 'curl --header token=abc-secret-123 example.com'
  [ "$status" -eq 2 ]
  echo "$output" | grep -qi "REDACTED"
  ! echo "$output" | grep -q "abc-secret-123"
}

# --- SEC-MED-2: env-var fallback for subagent_type ---

@test "SBB-MED2 CLAUDE_SUBAGENT_TYPE env triggers guard when JSON field missing" {
  local payload
  payload=$(jq -nc --arg c "cat src/x.ts" --arg sid "$CLAUDE_SESSION_ID" \
    '{tool_name:"Bash", tool_input:{command:$c}, session_id:$sid}')
  CLAUDE_SUBAGENT_TYPE="spec-blind-validator" run bash -c "echo '$payload' | bash '$HOOK'"
  [ "$status" -eq 2 ]
}

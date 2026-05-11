#!/usr/bin/env bats
# AC10 / AC5 / AC6 — spec-blind-validator read-guard.
# Verifies:
#   - plan.md and intake.md under pipeline-state/<id>/ are allowed
#   - src/** denied
#   - lib/interface.ts allowed (entry-point glob)
#   - lib/internal.ts denied (no entry-point match)
#   - src/index.ts allowed (R1 Eng #7 entry-point glob)
#   - other subagent_type fast-exits 0 — no JSONL written
#   - JSONL violation record is written on block

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/spec-blind-read-guard.sh"
  TMP="$(mktemp -d -t sbr.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="sbr-test-$$"
  # Pin CLAUDE_CONFIG_DIR to the worktree so the hook sources the helpers
  # we ship rather than the live install.
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

@test "SBR1 read of pipeline-state/foo/plan.md is allowed (exit 0)" {
  run _run_hook "spec-blind-validator" "Read" "$REPO_ROOT/pipeline-state/foo/plan.md"
  [ "$status" -eq 0 ]
}

@test "SBR2 read of pipeline-state/foo/intake.md is allowed" {
  run _run_hook "spec-blind-validator" "Read" "$REPO_ROOT/pipeline-state/foo/intake.md"
  [ "$status" -eq 0 ]
}

@test "SBR3 read of src/auth.ts is denied (exit 2 + JSONL)" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/src/auth.ts"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "BLOCKED: spec-blind-validator"
  # JSONL violation should exist
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  [ -f "$LOG" ]
  grep -q "spec_blind_blocked" "$LOG"
}

@test "SBR4 read of lib/interface.ts is allowed (entry-point glob)" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/lib/interface.ts"
  [ "$status" -eq 0 ]
}

@test "SBR5 read of lib/internal.ts is denied (no entry-point match)" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/lib/internal.ts"
  [ "$status" -eq 2 ]
}

@test "SBR6 read of src/index.ts is allowed (R1 Eng #7 entry-point)" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/src/index.ts"
  [ "$status" -eq 0 ]
}

@test "SBR7 read of __init__.py is allowed" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/myapp/__init__.py"
  [ "$status" -eq 0 ]
}

@test "SBR8 read of foo.openapi.yaml is allowed" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/api/users.openapi.yaml"
  [ "$status" -eq 0 ]
}

@test "SBR9 read of CLAUDE.md is allowed (test-runner discovery)" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/CLAUDE.md"
  [ "$status" -eq 0 ]
}

@test "SBR10 read of package.json is allowed" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/package.json"
  [ "$status" -eq 0 ]
}

@test "SBR11 other subagent_type fast-exits 0 even on src path" {
  run _run_hook "software-engineer" "Read" "/tmp/proj/src/auth.ts"
  [ "$status" -eq 0 ]
  # NO JSONL violation should be written for the other subagent
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  [ ! -f "$LOG" ]
}

@test "SBR-M1 Grep on src/** is denied (matcher coverage beyond Read)" {
  local payload
  payload=$(jq -nc --arg s "spec-blind-validator" --arg p "/tmp/proj/src/auth.ts" --arg sid "$CLAUDE_SESSION_ID" \
    '{tool_name:"Grep", subagent_type:$s, tool_input:{file_path:$p}, session_id:$sid}')
  run bash -c "echo '$payload' | bash '$HOOK'"
  [ "$status" -eq 2 ]
}

@test "SBR-M2 Glob with src/** pattern is denied" {
  local payload
  payload=$(jq -nc --arg s "spec-blind-validator" --arg p "/tmp/proj/src/**" --arg sid "$CLAUDE_SESSION_ID" \
    '{tool_name:"Glob", subagent_type:$s, tool_input:{pattern:$p}, session_id:$sid}')
  run bash -c "echo '$payload' | bash '$HOOK'"
  [ "$status" -eq 2 ]
}

@test "SBR-M3 relative src path is resolved against pwd and denied" {
  cd "$TMP" || return
  run _run_hook "spec-blind-validator" "Read" "src/auth.ts"
  [ "$status" -eq 2 ]
}

@test "SBR-M4 sanitised session_id with control chars produces clean log path" {
  # session_id with shell-meta chars must be stripped via tr -dc
  local payload
  payload=$(jq -nc --arg s "spec-blind-validator" --arg p "/tmp/proj/src/x.ts" --arg sid "evil$(printf '\\x01\\n')id" \
    '{tool_name:"Read", subagent_type:$s, tool_input:{file_path:$p}, session_id:$sid}')
  run bash -c "echo '$payload' | bash '$HOOK'"
  [ "$status" -eq 2 ]
  # No file should exist with control chars in name
  [ -z "$(find "$HOME/.claude/metrics" -type d -name '*evil*\\x01*' 2>/dev/null)" ]
}

@test "SBR12 read of node_modules path is denied (CR-MED-4: exclude pattern)" {
  # CR-MED-4: vendored / built / generated dirs are excluded BEFORE the
  # entry-point glob match so `**/index.{ts,js}` no longer admits
  # `node_modules/foo/index.js`. Excludes live in spec-blind-allow-paths.txt
  # as `!.*/node_modules/.*` etc.
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/node_modules/foo/index.js"
  [ "$status" -eq 2 ]
}

@test "SBR13 read of vendor/ path is denied (CR-MED-4: exclude pattern)" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/vendor/bundle/index.rb"
  [ "$status" -eq 2 ]
}

@test "SBR14 read of dist/ path is denied (CR-MED-4: exclude pattern)" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/dist/index.js"
  [ "$status" -eq 2 ]
}

@test "SBR15 read of build/ path is denied (CR-MED-4: exclude pattern)" {
  run _run_hook "spec-blind-validator" "Read" "/tmp/proj/build/index.js"
  [ "$status" -eq 2 ]
}

# --- SEC-HIGH-1: symlink bypass under read-guard ---

@test "SBR-SH1 symlink at allowlisted path -> src/ is denied (realpath check)" {
  PROJ="$TMP/proj"
  mkdir -p "$PROJ/src" "$PROJ/lib"
  echo "internal" > "$PROJ/src/internal.ts"
  # Symlink that LOOKS allowlisted (matches **/interface.ts ERE) but points at src/internal.ts.
  ln -s "$PROJ/src/internal.ts" "$PROJ/lib/interface.ts"
  run _run_hook "spec-blind-validator" "Read" "$PROJ/lib/interface.ts"
  # Realpath resolution lands on src/internal.ts which has no allowlist match -> denied.
  [ "$status" -eq 2 ]
}

@test "SBR-SH2 symlink at pipeline-state plan.md -> src/ is denied" {
  PROJ="$TMP/proj"
  mkdir -p "$PROJ/src" "$PROJ/pipeline-state/foo"
  echo "internal" > "$PROJ/src/internal.ts"
  ln -s "$PROJ/src/internal.ts" "$PROJ/pipeline-state/foo/plan.md"
  run _run_hook "spec-blind-validator" "Read" "$PROJ/pipeline-state/foo/plan.md"
  [ "$status" -eq 2 ]
}

# --- SEC-MED-2: env-var fallback for subagent_type ---

@test "SBR-MED2 CLAUDE_SUBAGENT_TYPE env var triggers guard when JSON field missing" {
  # Payload omits .subagent_type — without the fallback, the hook would fast-exit.
  local payload
  payload=$(jq -nc --arg p "/tmp/proj/src/auth.ts" --arg sid "$CLAUDE_SESSION_ID" \
    '{tool_name:"Read", tool_input:{file_path:$p}, session_id:$sid}')
  CLAUDE_SUBAGENT_TYPE="spec-blind-validator" run bash -c "echo '$payload' | bash '$HOOK'"
  [ "$status" -eq 2 ]
}

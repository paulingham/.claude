#!/usr/bin/env bats
# AC11 / AC7 — spec-blind-validator write-guard.
# Verifies:
#   - Writes under <repo-root>/tests/, /test/, /spec/, /__tests__/ are allowed
#   - Writes to src/** denied (exit 2 + JSONL)
#   - Writes to package.json denied (read-only manifest)
#   - Other subagent_type fast-exits 0
#   - SEC-HIGH-1: symlink-bypass attempts under tests/ pointing at src/ blocked
#   - SEC-HIGH-2: substring-match attacks (src/tests/, /etc/cron.d/tests/, ...) blocked

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/spec-blind-write-guard.sh"
  TMP="$(mktemp -d -t sbw.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="sbw-test-$$"
  export CLAUDE_CONFIG_DIR="$REPO_ROOT"
  export CLAUDE_HOOK_PROFILE="minimal"
  mkdir -p "$TMP/.claude"
  # SEC-HIGH-2: build a real git repo so the repo-root anchor in
  # is_path_allowed_for_spec_blind_write resolves. The previous fixture
  # under /tmp/proj/ was not a git repo and the new code rightly rejects it.
  PROJ="$TMP/proj"
  mkdir -p "$PROJ"
  git -C "$PROJ" init -q
  git -C "$PROJ" config user.email t@t
  git -C "$PROJ" config user.name t
  mkdir -p "$PROJ/tests" "$PROJ/test" "$PROJ/spec" "$PROJ/src/foo/__tests__" "$PROJ/lib"
  : > "$PROJ/.gitkeep" && git -C "$PROJ" add .gitkeep && git -C "$PROJ" commit -q -m init
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
  run _run_hook "spec-blind-validator" "Write" "$PROJ/tests/spec_blind_authored.test.ts"
  [ "$status" -eq 0 ]
}

@test "SBW2 write under spec/ is allowed" {
  run _run_hook "spec-blind-validator" "Write" "$PROJ/spec/users_spec.rb"
  [ "$status" -eq 0 ]
}

@test "SBW3 write under __tests__/ is allowed" {
  run _run_hook "spec-blind-validator" "Write" "$PROJ/src/foo/__tests__/foo.test.ts"
  [ "$status" -eq 0 ]
}

@test "SBW4 write to src/auth.ts is denied (exit 2 + JSONL)" {
  run _run_hook "spec-blind-validator" "Write" "$PROJ/src/auth.ts"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q "BLOCKED: spec-blind-validator may not write"
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  [ -f "$LOG" ]
  grep -q "spec_blind_blocked" "$LOG"
  grep -q "write-guard" "$LOG"
}

@test "SBW5 write to package.json is denied (read-only manifest)" {
  run _run_hook "spec-blind-validator" "Write" "$PROJ/package.json"
  [ "$status" -eq 2 ]
}

@test "SBW6 edit to interface.ts is denied (read-only)" {
  run _run_hook "spec-blind-validator" "Edit" "$PROJ/lib/interface.ts"
  [ "$status" -eq 2 ]
}

@test "SBW7 other subagent_type fast-exits 0 even on src write" {
  run _run_hook "software-engineer" "Write" "$PROJ/src/auth.ts"
  [ "$status" -eq 0 ]
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/spec-blind-violations.jsonl"
  [ ! -f "$LOG" ]
}

# --- SEC-HIGH-1: symlink bypass ---

@test "SBW-SH1 symlink under tests/ pointing at src/internal.ts is denied" {
  echo "internal" > "$PROJ/src/internal.ts"
  ln -s "$PROJ/src/internal.ts" "$PROJ/tests/sneaky.ts"
  run _run_hook "spec-blind-validator" "Write" "$PROJ/tests/sneaky.ts"
  # realpath resolves to src/internal.ts which is NOT under <repo-root>/{tests,test,spec,__tests__}/
  [ "$status" -eq 2 ]
}

# --- SEC-HIGH-2: substring-match write-allowlist attacks ---

@test "SBW-SH2 src/tests/foo.ts is denied (write into source tree)" {
  mkdir -p "$PROJ/src/tests"
  run _run_hook "spec-blind-validator" "Write" "$PROJ/src/tests/foo.ts"
  [ "$status" -eq 2 ]
}

@test "SBW-SH3 /etc/cron.d/tests/evil.sh is denied (absolute attack path)" {
  run _run_hook "spec-blind-validator" "Write" "/etc/cron.d/tests/evil.sh"
  [ "$status" -eq 2 ]
}

@test "SBW-SH4 ~/.ssh/tests/authorized_keys is denied (homedir attack path)" {
  run _run_hook "spec-blind-validator" "Write" "$HOME/.ssh/tests/authorized_keys"
  [ "$status" -eq 2 ]
}

@test "SBW-SH5 tests/../src/internal.ts is denied (path-traversal attempt)" {
  echo "internal" > "$PROJ/src/internal.ts"
  run _run_hook "spec-blind-validator" "Write" "$PROJ/tests/../src/internal.ts"
  # realpath resolves the .. so the final path is $PROJ/src/internal.ts — denied.
  [ "$status" -eq 2 ]
}

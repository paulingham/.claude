#!/usr/bin/env bats
# AC8 — vlm-critic-read-guard PreToolUse hook (Read|Grep|Glob).
# Per plan.md § 3 slice-b Failing test stubs (lines 128-132):
#   1. vlm_critic_read_of_src_returns_exit_2_with_jsonl_violation
#   2. vlm_critic_read_of_baseline_png_is_allowed
#   3. symlink_to_src_via_visual_baselines_path_blocked_by_realpath_resolution
#   4. violation_log_redacts_bearer_token_in_attempted_path
#
# Performance assertion (non_vlm_critic_subagent_fast_path_under_25ms) lives
# in tests/shell/test_vlm_critic_read_guard_perf.bats.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/vlm-critic-read-guard.sh"
  TMP="$(mktemp -d -t vlmcr.XXXXXX)"
  export HOME="$TMP"
  export CLAUDE_SESSION_ID="vlmcr-test-$$"
  # Pin CLAUDE_CONFIG_DIR to the worktree so the hook sources the helpers
  # we ship rather than the live install.
  export CLAUDE_PLUGIN_ROOT="$REPO_ROOT"  # HARNESS_ROOT only; keep HARNESS_DATA at $HOME so the violation log lands where the test reads it
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

# --- Plan-named test cases (slice-b Failing test stubs) ---

@test "VCR1 vlm_critic_read_of_src_returns_exit_2_with_jsonl_violation" {
  run _run_hook "vlm-critic" "Read" "/tmp/proj/src/foo.tsx"
  [ "$status" -eq 2 ]
  echo "$output" | grep -qF "BLOCKED:" || {
    echo "stderr/stdout missing BLOCKED token: $output" >&2
    false
  }
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/vlm-critic-violations.jsonl"
  [ -f "$LOG" ]
  grep -qF "vlm_critic_blocked" "$LOG"
}

@test "VCR2 vlm_critic_read_of_baseline_png_is_allowed" {
  run _run_hook "vlm-critic" "Read" \
    "/tmp/proj/pipeline-state/some-task/visual-baselines/home-desktop.png"
  [ "$status" -eq 0 ]
  # No JSONL violation log should be written.
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/vlm-critic-violations.jsonl"
  [ ! -f "$LOG" ]
}

@test "VCR3 symlink_to_src_via_visual_baselines_path_blocked_by_realpath_resolution" {
  # SEC-HIGH-1: a symlink at an allowlisted-looking path that points to
  # src/ must be blocked AFTER realpath resolution.
  PROJ="$TMP/proj"
  mkdir -p "$PROJ/src" "$PROJ/pipeline-state/task-1/visual-baselines"
  echo "internal source code" > "$PROJ/src/internal.tsx"
  ln -s "$PROJ/src/internal.tsx" \
    "$PROJ/pipeline-state/task-1/visual-baselines/leak.png"
  run _run_hook "vlm-critic" "Read" \
    "$PROJ/pipeline-state/task-1/visual-baselines/leak.png"
  # Realpath resolves to src/internal.tsx -> no allowlist match -> exit 2.
  [ "$status" -eq 2 ]
}

@test "VCR4 violation_log_redacts_bearer_token_in_attempted_path" {
  # SEC-MED-1: a Bearer token in the attempted path must be redacted in the
  # JSONL violation record.
  local path="/tmp/proj/src/Bearer abc123xyz/foo.tsx"
  run _run_hook "vlm-critic" "Read" "$path"
  [ "$status" -eq 2 ]
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/vlm-critic-violations.jsonl"
  [ -f "$LOG" ]
  # The original token must NOT appear; the redaction marker must.
  ! grep -qF "abc123xyz" "$LOG"
  grep -qF "***REDACTED***" "$LOG"
}

# --- Cross-tool matcher coverage (Grep, Glob) ---

@test "VCR-M1 Grep on src/** is denied (matcher coverage beyond Read)" {
  local payload
  payload=$(jq -nc --arg s "vlm-critic" --arg p "/tmp/proj/src/auth.ts" --arg sid "$CLAUDE_SESSION_ID" \
    '{tool_name:"Grep", subagent_type:$s, tool_input:{file_path:$p}, session_id:$sid}')
  run bash -c "echo '$payload' | bash '$HOOK'"
  [ "$status" -eq 2 ]
}

@test "VCR-M2 Glob with src/** pattern is denied" {
  local payload
  payload=$(jq -nc --arg s "vlm-critic" --arg p "/tmp/proj/src/**" --arg sid "$CLAUDE_SESSION_ID" \
    '{tool_name:"Glob", subagent_type:$s, tool_input:{pattern:$p}, session_id:$sid}')
  run bash -c "echo '$payload' | bash '$HOOK'"
  [ "$status" -eq 2 ]
}

# --- Other subagent fast-path (no JSONL written, exit 0) ---

@test "VCR5 other subagent_type fast-exits 0 even on src path" {
  run _run_hook "software-engineer" "Read" "/tmp/proj/src/auth.ts"
  [ "$status" -eq 0 ]
  LOG="$HOME/.claude/metrics/$CLAUDE_SESSION_ID/vlm-critic-violations.jsonl"
  [ ! -f "$LOG" ]
}

# --- Plan.md is in allowlist ---

@test "VCR6 vlm-critic read of pipeline-state plan.md is allowed" {
  run _run_hook "vlm-critic" "Read" \
    "$REPO_ROOT/pipeline-state/foo/plan.md"
  [ "$status" -eq 0 ]
}

# --- SEC-MED-2 env-var fallback ---

@test "VCR-MED2 CLAUDE_SUBAGENT_TYPE env var triggers guard when JSON field missing" {
  # Payload omits .subagent_type — without the fallback the hook would fast-exit.
  local payload
  payload=$(jq -nc --arg p "/tmp/proj/src/auth.ts" --arg sid "$CLAUDE_SESSION_ID" \
    '{tool_name:"Read", tool_input:{file_path:$p}, session_id:$sid}')
  CLAUDE_SUBAGENT_TYPE="vlm-critic" run bash -c "echo '$payload' | bash '$HOOK'"
  [ "$status" -eq 2 ]
}

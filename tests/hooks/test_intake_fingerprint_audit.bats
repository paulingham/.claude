#!/usr/bin/env bats
# Slice B — AC5 (hooks/intake-fingerprint-audit.sh)
# Verifies the PostToolUse hook:
#   (i)   Writes a JSONL line on Skill matcher with proper schema
#   (ii)  Early-exits on non-Skill tool_name
#   (iii) Respects CLAUDE_HOOK_PROFILE=minimal
#   (iv)  Exits 0 on every path
#   (v)   Resolves task_id from tool_response parse of [Intake] task_id: marker

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/intake-fingerprint-audit.sh"
  TMP_DIR="$(mktemp -d -t intake-fingerprint-audit-XXXXXX)"
  export CLAUDE_HOOK_LOG_DIR="$TMP_DIR/metrics"
  export CLAUDE_SESSION_ID="test-session"
  export CLAUDE_CONFIG_DIR="$TMP_DIR/config"
  mkdir -p "$CLAUDE_CONFIG_DIR/pipeline-state/foo-bar"
  cat > "$CLAUDE_CONFIG_DIR/pipeline-state/foo-bar/intake.md" <<'EOF'
---
task_id: foo-bar
tier_emitted: T5
tier_initial: T5
detector_phase: rules
detector_confidence: high
user_phrasing_signals: []
phrasing_honoured: true
override_token: null
safety_override_fired: false
predicted_files: []
fingerprint_cost_tokens: 0
criticality_filtered_by_tier: false
---
EOF
  unset CLAUDE_HOOK_PROFILE
}

teardown() {
  if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
    find "$TMP_DIR" -type f -delete
    find "$TMP_DIR" -depth -type d -empty -delete
  fi
}

@test "test_hook_writes_jsonl_when_skill_is_intake" {
  local input='{"tool_name":"Skill","tool_response":"[Intake] task_id: foo-bar\n[Intake] Tier: T5"}'
  run bash -c "echo '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/test-session/intake-overrides.jsonl"
  [ -f "$jsonl_path" ]
  [ "$(wc -l < "$jsonl_path")" -eq 1 ]
  python3 -c "import json,sys; rec=json.loads(open('$jsonl_path').read().strip()); \
    keys=['timestamp','task_id','tier_emitted','tier_initial','detector_phase','detector_confidence', \
          'user_phrasing_signals','phrasing_honoured','override_token','safety_override_fired', \
          'predicted_files','fingerprint_cost_tokens']; \
    missing=[k for k in keys if k not in rec]; sys.exit(1 if missing else 0)"
}

@test "test_hook_early_exits_on_non_skill" {
  local input='{"tool_name":"Bash","tool_response":"some output"}'
  run bash -c "echo '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/test-session/intake-overrides.jsonl"
  [ ! -f "$jsonl_path" ]
}

@test "test_hook_respects_minimal_profile" {
  export CLAUDE_HOOK_PROFILE=minimal
  local input='{"tool_name":"Skill","tool_response":"[Intake] task_id: foo-bar"}'
  run bash -c "echo '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/test-session/intake-overrides.jsonl"
  [ ! -f "$jsonl_path" ]
}

@test "test_hook_exits_zero_on_every_path" {
  # Missing intake.md — still exits 0, still writes JSONL with parse_error
  rm -f "$CLAUDE_CONFIG_DIR/pipeline-state/foo-bar/intake.md"
  local input='{"tool_name":"Skill","tool_response":"[Intake] task_id: foo-bar"}'
  run bash -c "echo '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/test-session/intake-overrides.jsonl"
  [ -f "$jsonl_path" ]
  grep -q 'intake-md-missing' "$jsonl_path"
}

@test "test_task_id_resolved_from_tool_response" {
  # No [Intake] task_id: marker → parse_error: task-id-resolution-failed
  local input='{"tool_name":"Skill","tool_response":"some other output"}'
  run bash -c "echo '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/test-session/intake-overrides.jsonl"
  [ -f "$jsonl_path" ]
  grep -q 'task-id-resolution-failed' "$jsonl_path"
  grep -q '"task_id": "<unknown>"' "$jsonl_path"
}

#!/usr/bin/env bats
# Slice E — ACs E1, E2, E3, E5 for hooks/plan-cache-audit.sh.
# Mirrors tests/hooks/test_intake_fingerprint_audit.bats shape.
# Verifies the PostToolUse hook:
#   E1: HIT verdict produces JSONL line with all REQUIRED_KEYS
#   E2: non-plan-cache Skill produces no JSONL (no [PlanCacheLookup] marker)
#   E3: non-Skill tool invocations short-circuit before tool_response parse
#   E5: HIT JSONL line carries adapter_cost_tokens numeric field

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/plan-cache-audit.sh"
  TMP_DIR="$(mktemp -d -t plan-cache-audit-XXXXXX)"
  export CLAUDE_HOOK_LOG_DIR="$TMP_DIR/metrics"
  export CLAUDE_SESSION_ID="test-session"
  export CLAUDE_CONFIG_DIR="$TMP_DIR/config"
  mkdir -p "$CLAUDE_CONFIG_DIR/pipeline-state/foo-bar"
  cat > "$CLAUDE_CONFIG_DIR/pipeline-state/foo-bar/intake.md" <<'EOF'
---
task_id: foo-bar
---
EOF
  unset CLAUDE_HOOK_PROFILE
  unset CLAUDE_PLAN_CACHE_ADAPTER_TOKENS
}

teardown() {
  if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
    find "$TMP_DIR" -type f -delete
    find "$TMP_DIR" -depth -type d -empty -delete
  fi
}

@test "E1 HIT verdict produces JSONL line with all REQUIRED_KEYS" {
  export CLAUDE_PLAN_CACHE_TASK_ID="foo-bar"
  local marker='[PlanCacheLookup] {"verdict":"PLAN_CACHE_HIT","cache_key":"abc123"}'
  local input
  input=$(jq -cn --arg r "$marker" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/test-session/plan-cache.jsonl"
  [ -f "$jsonl_path" ]
  [ "$(wc -l < "$jsonl_path")" -eq 1 ]
  python3 -c "import json,sys; rec=json.loads(open('$jsonl_path').read().strip()); \
    keys=['task_id','cache_key','verdict','adapter_cost_tokens','miss_reason', \
          'hit_template_path','hit_count_after','pv_outcome','session_id']; \
    missing=[k for k in keys if k not in rec]; sys.exit(1 if missing else 0)"
}

@test "E2 non-plan-cache Skill produces no JSONL" {
  local input='{"tool_name":"Skill","tool_response":"[Intake] task_id: foo-bar"}'
  run bash -c "printf '%s' '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/test-session/plan-cache.jsonl"
  [ ! -f "$jsonl_path" ]
}

@test "E3 non-Skill tool invocations short-circuit before tool_response parse" {
  local input='{"tool_name":"Edit","tool_response":"[PlanCacheLookup] should not match"}'
  run bash -c "printf '%s' '$input' | bash '$HOOK' 2>&1"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/test-session/plan-cache.jsonl"
  [ ! -f "$jsonl_path" ]
  [ -z "$output" ]
}

@test "E5 HIT JSONL line carries adapter_cost_tokens numeric field" {
  export CLAUDE_PLAN_CACHE_TASK_ID="foo-bar"
  export CLAUDE_PLAN_CACHE_ADAPTER_TOKENS=2500
  local marker='[PlanCacheLookup] {"verdict":"PLAN_CACHE_HIT","cache_key":"k1"}'
  local input
  input=$(jq -cn --arg r "$marker" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/test-session/plan-cache.jsonl"
  [ -f "$jsonl_path" ]
  python3 -c "import json,sys; rec=json.loads(open('$jsonl_path').read().strip()); \
    v=rec.get('adapter_cost_tokens'); \
    sys.exit(0 if isinstance(v,(int,float)) and v==2500 else 1)"
}

@test "E5b MISS JSONL line still carries adapter_cost_tokens as numeric (default 0)" {
  export CLAUDE_PLAN_CACHE_TASK_ID="foo-bar"
  local marker='[PlanCacheLookup] {"verdict":"PLAN_CACHE_MISS","reason":"no-template","cache_key":"k2"}'
  local input
  input=$(jq -cn --arg r "$marker" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/test-session/plan-cache.jsonl"
  [ -f "$jsonl_path" ]
  python3 -c "import json,sys; rec=json.loads(open('$jsonl_path').read().strip()); \
    v=rec.get('adapter_cost_tokens'); \
    mr=rec.get('miss_reason'); \
    sys.exit(0 if isinstance(v,(int,float)) and v==0 and mr=='no-template' else 1)"
}

@test "E_hook_exits_zero_on_every_path" {
  # Malformed JSON input — still exits 0
  local input='not json at all'
  run bash -c "printf '%s' '$input' | bash '$HOOK' 2>&1"
  [ "$status" -eq 0 ]
}

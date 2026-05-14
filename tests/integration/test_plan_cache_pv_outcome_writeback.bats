#!/usr/bin/env bats
# Slice E — AC E6: pv_outcome field populated after Plan Validation completes.
# When a [PlanValidationOutcome] marker arrives later in the same session,
# the most recent HIT line in plan-cache.jsonl is rewritten with pv_outcome
# set to the PV verdict.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  HOOK="$REPO_ROOT/hooks/plan-cache-audit.sh"
  TMP_DIR="$(mktemp -d -t plan-cache-pv-XXXXXX)"
  export CLAUDE_HOOK_LOG_DIR="$TMP_DIR/metrics"
  export CLAUDE_SESSION_ID="pv-session"
  export CLAUDE_CONFIG_DIR="$TMP_DIR/config"
  export CLAUDE_PLAN_CACHE_TASK_ID="foo-bar"
  mkdir -p "$CLAUDE_CONFIG_DIR/pipeline-state/foo-bar"
  cat > "$CLAUDE_CONFIG_DIR/pipeline-state/foo-bar/intake.md" <<'EOF'
---
task_id: foo-bar
---
EOF
}

teardown() {
  if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
    find "$TMP_DIR" -type f -delete
    find "$TMP_DIR" -depth -type d -empty -delete
  fi
}

@test "E6 pv_outcome=PLAN_APPROVED is written back to latest HIT line" {
  local hit='[PlanCacheLookup] {"verdict":"PLAN_CACHE_HIT","cache_key":"kPV"}'
  local hit_input pv_input
  hit_input=$(jq -cn --arg r "$hit" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$hit_input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/pv-session/plan-cache.jsonl"
  [ -f "$jsonl_path" ]
  python3 -c "import json; rec=json.loads(open('$jsonl_path').read().strip()); \
    assert rec['pv_outcome'] in (None, '', '<pending>'), rec"

  # Now synthesise the Plan Validation completion event.
  local pv='[PlanValidationOutcome] verdict: PLAN_APPROVED'
  pv_input=$(jq -cn --arg r "$pv" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$pv_input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  [ "$(wc -l < "$jsonl_path")" -eq 1 ]
  python3 -c "import json,sys; rec=json.loads(open('$jsonl_path').read().strip()); \
    sys.exit(0 if rec.get('pv_outcome')=='PLAN_APPROVED' else 1)"
}

@test "E6b pv_outcome=PLAN_HOLES is accepted as a valid PV verdict" {
  local hit='[PlanCacheLookup] {"verdict":"PLAN_CACHE_HIT","cache_key":"kHoles"}'
  local hit_input pv_input
  hit_input=$(jq -cn --arg r "$hit" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$hit_input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local pv='[PlanValidationOutcome] verdict: PLAN_HOLES'
  pv_input=$(jq -cn --arg r "$pv" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$pv_input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl_path="$CLAUDE_HOOK_LOG_DIR/pv-session/plan-cache.jsonl"
  python3 -c "import json,sys; rec=json.loads(open('$jsonl_path').read().strip()); \
    sys.exit(0 if rec.get('pv_outcome')=='PLAN_HOLES' else 1)"
}

#!/usr/bin/env bats
# Slice F — AC F7 end-to-end integration.
# Plan: pipeline-state/plan-cache-agentic/plan.md § slice-f-shadow-mode-rollout F7.
#
# Confirms the producer (skills/plan-self-validation/_lib/emit_outcome.sh)
# emits a marker the slice-e consumer (hooks/plan-cache-audit.sh) accepts and
# writes back to plan-cache.jsonl as `pv_outcome`. Without this end-to-end
# proof, the contract is testable only at the marker-shape level.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  EMIT="$REPO_ROOT/skills/plan-self-validation/_lib/emit_outcome.sh"
  HOOK="$REPO_ROOT/hooks/plan-cache-audit.sh"
  TMP_DIR="$(mktemp -d -t plan-cache-pv-e2e-XXXXXX)"
  export CLAUDE_HOOK_LOG_DIR="$TMP_DIR/metrics"
  export CLAUDE_SESSION_ID="pv-e2e-session"
  export CLAUDE_PLAN_CACHE_TASK_ID="e2e-task"
}

teardown() {
  if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
    find "$TMP_DIR" -type f -delete
    find "$TMP_DIR" -depth -type d -empty -delete
  fi
}

@test "F7-E2E producer marker → consumer pv_outcome writeback (PLAN_APPROVED)" {
  # 1. Synthesise a HIT line in JSONL via the audit hook.
  local hit hit_input
  hit='[PlanCacheLookup] {"verdict":"PLAN_CACHE_HIT","cache_key":"kE2E"}'
  hit_input=$(jq -cn --arg r "$hit" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$hit_input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl="$CLAUDE_HOOK_LOG_DIR/pv-e2e-session/plan-cache.jsonl"
  [ -f "$jsonl" ]

  # 2. Capture the producer marker.
  local marker
  marker=$("$EMIT" PLAN_APPROVED)
  printf '%s\n' "$marker" | grep -qE '^\[PlanValidationOutcome\] verdict: PLAN_APPROVED$'

  # 3. Feed the marker to the consumer hook (as it would arrive in a
  #    Skill tool_response).
  local pv_input
  pv_input=$(jq -cn --arg r "$marker" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$pv_input' | bash '$HOOK'"
  [ "$status" -eq 0 ]

  # 4. Assert pv_outcome is populated on the HIT line.
  python3 -c "
import json, sys
rec = json.loads(open('$jsonl').read().strip())
sys.exit(0 if rec.get('pv_outcome') == 'PLAN_APPROVED' else 1)
"
}

@test "F7-E2E producer marker → consumer pv_outcome writeback (PLAN_HOLES)" {
  local hit hit_input
  hit='[PlanCacheLookup] {"verdict":"PLAN_CACHE_HIT","cache_key":"kE2E2"}'
  hit_input=$(jq -cn --arg r "$hit" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$hit_input' | bash '$HOOK'"
  [ "$status" -eq 0 ]
  local jsonl="$CLAUDE_HOOK_LOG_DIR/pv-e2e-session/plan-cache.jsonl"

  local marker pv_input
  marker=$("$EMIT" PLAN_HOLES)
  pv_input=$(jq -cn --arg r "$marker" '{tool_name:"Skill",tool_response:$r}')
  run bash -c "printf '%s' '$pv_input' | bash '$HOOK'"
  [ "$status" -eq 0 ]

  python3 -c "
import json, sys
rec = json.loads(open('$jsonl').read().strip())
sys.exit(0 if rec.get('pv_outcome') == 'PLAN_HOLES' else 1)
"
}

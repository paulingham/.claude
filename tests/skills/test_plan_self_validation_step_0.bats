#!/usr/bin/env bats
# GEAR MIGRATION: plan-self-validation Step 0 re-fingerprint -> re-gear-check
# Verifies:
#   - "### Step 0: Re-fingerprint sanity check" exists BETWEEN "## Process" and "### Step 1: Read the Plan"
#   - rules/core.md path-pattern check is documented (per HIGH-1) — this floor is KEPT
#   - State-file template has gear_initial, gear_replanned, routing_upshifted
#   - Verdict enum extended to include ROUTING_UPSHIFTED

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PSV_SKILL="$REPO_ROOT/skills/plan-self-validation/SKILL.md"
}

@test "test_step_0_re_fingerprint_present" {
  grep -E '^### Step 0: Re-fingerprint sanity check' "$PSV_SKILL"
}

@test "test_step_0_orders_between_process_and_step_1" {
  local proc s0 s1
  proc=$(grep -n -E '^## Process' "$PSV_SKILL" | head -1 | cut -d: -f1)
  s0=$(grep -n -E '^### Step 0:' "$PSV_SKILL" | head -1 | cut -d: -f1)
  s1=$(grep -n -E '^### Step 1: Read the Plan' "$PSV_SKILL" | head -1 | cut -d: -f1)
  [ -n "$proc" ] && [ -n "$s0" ] && [ -n "$s1" ]
  [ "$proc" -lt "$s0" ]
  [ "$s0" -lt "$s1" ]
}

@test "test_step_0_documents_rules_core_md_path_pattern" {
  grep -E 'rules/core\.md' "$PSV_SKILL"
}

@test "test_state_file_template_includes_routing_keys" {
  local key
  for key in gear_initial gear_replanned routing_upshifted; do
    grep -qE "${key}:" "$PSV_SKILL" || { echo "missing key: ${key}"; return 1; }
  done
}

@test "test_verdict_enum_includes_routing_upshifted" {
  grep -E 'ROUTING_UPSHIFTED' "$PSV_SKILL"
  # Enum must literally include ROUTING_UPSHIFTED alongside PLAN_APPROVED/PLAN_HOLES
  grep -E 'PLAN_APPROVED.*PLAN_HOLES.*ROUTING_UPSHIFTED|PLAN_APPROVED.*ROUTING_UPSHIFTED|ROUTING_UPSHIFTED.*PLAN_APPROVED' "$PSV_SKILL"
}

@test "test_step_0_documents_safety_upshift_floor_to_pipeline" {
  grep -E 'upshift.*PIPELINE|PIPELINE.*upshift' "$PSV_SKILL"
}

@test "test_step_0_documents_affected_files_input" {
  grep -E 'Affected Files|affected.files|affected_files' "$PSV_SKILL"
}

@test "test_verdict_consistency_callable_passes_against_psv_skill" {
  # The new ROUTING_UPSHIFTED verdict in plan-self-validation skill must be
  # consistent with protocols/verdict-catalog.md per Slice A's callable.
  bash "$REPO_ROOT/hooks/_lib/verdict-consistency-check.sh"
}

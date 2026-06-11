#!/usr/bin/env bats
# Slice B — AC6 (pipeline Step 1.0 Tier Guard)
# Verifies skills/pipeline/SKILL.md contains:
#   - "### Step 1.0: Tier Guard" header BEFORE "### Step 1: Classify Work"
#   - All seven tier routes T0..T6 named
#   - Explicit "Pipeline halts (NO state file created)" verbiage for T0-T3
#   - [Pipeline] Tier guard: status line marker

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PIPELINE_SKILL="$REPO_ROOT/skills/pipeline/SKILL.md"
}

@test "test_step_1_0_tier_guard_present" {
  grep -E '^### Step 1\.0: Tier Guard' "$PIPELINE_SKILL"
}

@test "test_step_1_0_orders_before_step_1" {
  local s10 s1
  s10=$(grep -n -E '^### Step 1\.0:' "$PIPELINE_SKILL" | head -1 | cut -d: -f1)
  s1=$(grep -n -E '^### Step 1: Classify Work' "$PIPELINE_SKILL" | head -1 | cut -d: -f1)
  [ -n "$s10" ] && [ -n "$s1" ]
  [ "$s10" -lt "$s1" ]
}

@test "test_step_1_0_names_all_seven_tier_routes" {
  local tier
  for tier in T0 T1 T2 T3 T4 T5 T6; do
    grep -qE "${tier}\b" "$PIPELINE_SKILL" || { echo "missing tier: ${tier}"; return 1; }
  done
}

@test "test_step_1_0_forbids_state_file_for_T0_T3" {
  grep -E 'Pipeline halts \(NO state file created\)' "$PIPELINE_SKILL"
}

@test "test_step_1_0_emits_status_line" {
  grep -E '\[Pipeline\] Tier guard:' "$PIPELINE_SKILL"
}

@test "test_step_1_0_routes_T0_to_answer_or_techspike" {
  grep -E 'T0.*tech-spike|T0.*direct answer|tech-spike.*T0|direct answer.*T0' "$PIPELINE_SKILL"
}

@test "test_step_1_0_routes_T1_to_worktree_subagent" {
  grep -E 'T1.*worktree|worktree.*T1' "$PIPELINE_SKILL"
}

@test "test_step_1_0_routes_T2_to_harness_config" {
  grep -E 'T2.*harness-config|harness-config.*T2' "$PIPELINE_SKILL"
}

@test "test_step_1_0_routes_T3_to_batch_pipeline" {
  grep -E 'T3.*batch-pipeline|batch-pipeline.*T3' "$PIPELINE_SKILL"
}

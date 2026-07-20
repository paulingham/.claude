#!/usr/bin/env bats
# GEAR MIGRATION: pipeline Step 1.0 Tier Guard -> Gear Guard
# Verifies skills/pipeline/SKILL.md contains:
#   - "### Step 1.0: Gear Guard" header BEFORE "### Step 1: Classify Work"
#   - All three gear routes PAIR/BUILD/PIPELINE named
#   - Explicit "Pipeline halts (NO state file created)" verbiage for PAIR
#   - [Pipeline] Gear guard: status line marker
#   - missing-gear default routes to PIPELINE (safety-bias)

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PIPELINE_SKILL="$REPO_ROOT/skills/pipeline/SKILL.md"
}

@test "test_step_1_0_gear_guard_present" {
  grep -E '^### Step 1\.0: Gear Guard' "$PIPELINE_SKILL"
}

@test "test_step_1_0_orders_before_step_1" {
  local s10 s1
  s10=$(grep -n -E '^### Step 1\.0:' "$PIPELINE_SKILL" | head -1 | cut -d: -f1)
  s1=$(grep -n -E '^### Step 1: Classify Work' "$PIPELINE_SKILL" | head -1 | cut -d: -f1)
  [ -n "$s10" ] && [ -n "$s1" ]
  [ "$s10" -lt "$s1" ]
}

@test "test_step_1_0_names_all_three_gear_routes" {
  local gear
  for gear in PAIR BUILD PIPELINE; do
    grep -qE "\*\*${gear}\*\*" "$PIPELINE_SKILL" || { echo "missing gear: ${gear}"; return 1; }
  done
}

@test "test_step_1_0_forbids_state_file_for_PAIR" {
  grep -E 'Pipeline halts \(NO state file created\)' "$PIPELINE_SKILL"
}

@test "test_step_1_0_emits_status_line" {
  grep -E '\[Pipeline\] Gear guard:' "$PIPELINE_SKILL"
}

@test "test_step_1_0_routes_PAIR_to_subbehaviour" {
  grep -E 'PAIR.*halt.*re-route|PAIR.*sub-behaviour' "$PIPELINE_SKILL"
}

@test "test_step_1_0_routes_BUILD_to_lightweight_or_standard" {
  grep -E 'BUILD.*lightweight|BUILD.*standard' "$PIPELINE_SKILL"
}

@test "test_step_1_0_routes_PIPELINE_to_heavy" {
  grep -E 'PIPELINE.*heavy|heavy.*PIPELINE' "$PIPELINE_SKILL"
}

@test "test_step_1_0_missing_gear_defaults_to_PIPELINE" {
  grep -E 'gear_emitted.*missing.*PIPELINE|missing.*default.*PIPELINE|default to \*\*PIPELINE\*\*' "$PIPELINE_SKILL"
}

@test "test_step_1_0_has_no_T3H_trimmed_lane_prose" {
  # WHY: the T3H CONTINUE-tier + scope-overflow-abort concept is retired
  # entirely with the T0-T6 fingerprint. RED if it survives the rewrite.
  ! grep -qE 'T3H|trimmed lane|Scope-overflow abort' "$PIPELINE_SKILL"
}

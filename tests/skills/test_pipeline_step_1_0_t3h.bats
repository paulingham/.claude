#!/usr/bin/env bats
# Slice D — ACs D1, D4, D5, D6
# Verifies skills/pipeline/SKILL.md Step 1.0 Tier Guard contains:
#   D1  T3H CONTINUE row → Build + diff-only code-review + Ship; skips Plan/PlanVal/SecReview
#   D4  T3H code-review is diff-only standard reviewer (no new agent)
#   D5  scope-overflow abort rule (>1 file OR >15 changed lines → abort, upshift T4, re-enter Plan)
#   D6  T3H runs Reflect AND emits deploy_outcome with tier_emitted:T3H

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PIPELINE_SKILL="$REPO_ROOT/skills/pipeline/SKILL.md"
}

@test "test_step_1_0_routes_T3H_to_trimmed_continue_lane" {
  # D1: T3H CONTINUE row present; trimmed lane names Build + diff-only code-review + Ship;
  # explicitly skips Plan, Plan-Validation, Security-Review
  grep -qE 'T3H' "$PIPELINE_SKILL" || { echo "T3H not found in pipeline SKILL.md"; return 1; }
  grep -qE 'trimmed' "$PIPELINE_SKILL" || { echo "trimmed lane not found"; return 1; }
  grep -qE 'SKIP.*(Plan|Plan-Validation|Security-Review)' "$PIPELINE_SKILL" \
    || { echo "SKIP clause for Plan/PlanVal/SecReview not found"; return 1; }
}

@test "test_T3H_code_review_is_diff_only_standard_reviewer" {
  # D4: T3H specifies standard code-reviewer diff-only (no new agent invented)
  grep -qE 'diff-only' "$PIPELINE_SKILL" \
    || { echo "diff-only code-review not found for T3H"; return 1; }
  grep -qE 'standard code-reviewer|code-reviewer.*diff-only|diff-only.*code-reviewer' "$PIPELINE_SKILL" \
    || { echo "standard code-reviewer diff-only not found"; return 1; }
}

@test "test_T3H_scope_overflow_aborts_and_upshifts_to_T4" {
  # D5: scope-overflow abort rule present:
  #   diff >1 file OR >15 changed lines → ABORT trimmed lane, upshift T4, re-enter Plan
  grep -qE 'scope.overflow|ABORT.*trimmed|trimmed.*ABORT' "$PIPELINE_SKILL" \
    || { echo "scope-overflow abort rule not found"; return 1; }
  grep -qE 'upshift.*T4|T4.*upshift' "$PIPELINE_SKILL" \
    || { echo "upshift to T4 not found"; return 1; }
  grep -qE '1 file|15 (changed )?lines' "$PIPELINE_SKILL" \
    || { echo "overflow threshold (1 file / 15 lines) not found"; return 1; }
}

@test "test_T3H_runs_reflect_and_emits_tier_emitted_telemetry" {
  # D6: T3H still runs Reflect (Iron Law 7) AND emits deploy_outcome with tier_emitted:T3H
  grep -qE 'T3H.*Reflect|Reflect.*T3H' "$PIPELINE_SKILL" \
    || { echo "T3H Reflect requirement not found"; return 1; }
  grep -qE 'tier_emitted.*T3H|T3H.*tier_emitted' "$PIPELINE_SKILL" \
    || { echo "tier_emitted:T3H telemetry not found"; return 1; }
  grep -qE 'deploy_outcome' "$PIPELINE_SKILL" \
    || { echo "deploy_outcome companion record not found"; return 1; }
}

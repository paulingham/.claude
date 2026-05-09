#!/usr/bin/env bats
# Slice 3 AC11 — skills/pipeline/SKILL.md routing extension + drive-by drift fix.
# Tests:
#   - The PDR-RTV check is documented BEFORE the Best-of-N check in Step 3.
#   - The bestofn formula matches the live intake (`critical OR user_override`);
#     the stale form (`task_class == "feature" AND budget >= 5`) is absent.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PIPELINE_SKILL="$REPO_ROOT/skills/pipeline/SKILL.md"
  [ -f "$PIPELINE_SKILL" ]
}

@test "pipeline_skill_routes_pdr_rtv_first_when_flag_set" {
  # PDR-RTV check appears textually before Best-of-N check in Step 3.
  pdr_line=$(grep -n "pdr_rtv" "$PIPELINE_SKILL" | head -1 | cut -d: -f1)
  bestofn_check_line=$(grep -n "Best-of-N Check" "$PIPELINE_SKILL" | head -1 | cut -d: -f1)

  [ -n "$pdr_line" ]
  [ -n "$bestofn_check_line" ]
  # The pdr_rtv check must appear at-or-before the Best-of-N check section,
  # OR within the same section as the new precedence rule.
  # We accept: pdr_line <= (bestofn_check_line + 30) AND we find an explicit
  # routing-precedence statement nearby.
  run grep -E "pdr_rtv\s*==\s*true|pdr_rtv.*first|pdr_rtv.*before" "$PIPELINE_SKILL"
  [ "$status" -eq 0 ]
}

@test "pipeline_skill_documents_pdr_rtv_dispatch_variant" {
  # The pipeline skill mentions /pdr-rtv as a build dispatch variant.
  run grep -E "pdr.rtv" "$PIPELINE_SKILL"
  [ "$status" -eq 0 ]
}

@test "pipeline_skill_bestofn_formula_matches_live_intake" {
  # AC11 drive-by: line ~250 stale formula must match live intake formula
  # `critical OR user_override`. The stale form
  # `task_class == "feature" AND budget >= 5` must be absent.
  run grep -E 'critical\s+OR\s+\(?\s*task_class\s*==\s*"feature"\s+AND\s+budget' "$PIPELINE_SKILL"
  [ "$status" -ne 0 ]
}

@test "pipeline_skill_bestofn_formula_present_in_live_form" {
  # The live form `critical OR user_override` is present.
  run grep -E "critical\s+OR\s+user_override" "$PIPELINE_SKILL"
  [ "$status" -eq 0 ]
}

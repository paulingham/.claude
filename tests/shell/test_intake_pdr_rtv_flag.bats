#!/usr/bin/env bats
# Slice 3 AC14 — intake Step 2d-bis pdr_rtv flag computation.
#
# Tests the documentation contract — `skills/intake/SKILL.md` Step 2d-bis
# must specify:
#   - pdr_rtv = budget >= ${CLAUDE_PDR_RTV_BUDGET_FLOOR:-9} OR critical == true
#   - default trigger floor is 9 (NOT 7)
#   - flag persisted to pipeline-state/{task-id}/intake.md frontmatter
# AC14 is documentation-encoded (mirrors how bestofn formula is documented
# in Step 2d-bis); the runtime computation lives in the orchestrator's
# intake invocation. Tests grep the source-of-truth document.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  INTAKE_SKILL="$REPO_ROOT/skills/intake/SKILL.md"
  [ -f "$INTAKE_SKILL" ]
}

@test "intake_writes_pdr_rtv_flag_when_budget_ge_9" {
  # AC14 — Intake Step 2d-bis documents pdr_rtv flag computation with
  # default floor `budget >= 9`.
  run grep -E "pdr_rtv" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
  # Default floor 9 with env-var override.
  run grep -E "CLAUDE_PDR_RTV_BUDGET_FLOOR" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
  # Documents the formula (budget >= floor OR critical).
  run grep -E "budget\s*>=\s*\\\$\{CLAUDE_PDR_RTV_BUDGET_FLOOR:-9\}\s+OR\s+critical" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
}

@test "intake_persists_pdr_rtv_to_intake_md_frontmatter" {
  # The skill must specify that pdr_rtv is written to intake.md frontmatter.
  run grep -E "pdr_rtv:\s*(true|false|\\{true\\|false\\})" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
}

@test "intake_honors_pdr_rtv_budget_floor_env_override" {
  # The env var override is documented and the range (5-15) is mentioned.
  # We accept any documentation that mentions the env var with default 9.
  run grep -E "CLAUDE_PDR_RTV_BUDGET_FLOOR" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
  # The default-9 floor is documented.
  run grep -E ":-9}|default.*9|default 9" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
}

@test "intake_documents_pdr_rtv_default_floor_not_7" {
  # The default floor is 9, not 7. Old budget>=7 default must NOT be present
  # for pdr_rtv (it's mentioned in the migration plan in pdr-rtv anti-patterns,
  # but the live formula in intake must use 9).
  # Specifically: in the intake skill, the formula should not say
  # `${CLAUDE_PDR_RTV_BUDGET_FLOOR:-7}`.
  run grep -E "CLAUDE_PDR_RTV_BUDGET_FLOOR:-7" "$INTAKE_SKILL"
  [ "$status" -ne 0 ]
}

@test "intake_pdr_rtv_formula_uses_OR_not_AND" {
  # Mutation guard: the formula combines two clauses with OR, not AND.
  # If a future edit accidentally changes it to AND, this test fires.
  # Look for the pdr_rtv formula line specifically with OR critical.
  run grep -E "pdr_rtv\s*=\s*budget\s*>=\s*\\\$\{CLAUDE_PDR_RTV_BUDGET_FLOOR:-9\}\s+OR\s+critical" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
}

@test "intake_pdr_rtv_formula_uses_ge_not_gt" {
  # Mutation guard: the formula uses >= (greater-or-equal), not > (greater-than).
  # The default floor is 9, and budget==9 must trigger PDR-RTV.
  run grep -E "pdr_rtv\s*=\s*budget\s*>=\s*" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
  # Negative: bare `>` should not appear in the formula (without =).
  # This is a sanity check; the positive grep above is the main guard.
  run grep -E "pdr_rtv\s*=\s*budget\s*>\s+\\\$" "$INTAKE_SKILL"
  [ "$status" -ne 0 ]
}

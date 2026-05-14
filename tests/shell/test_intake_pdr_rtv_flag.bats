#!/usr/bin/env bats
# Intake Step 2d-bis pdr_rtv flag computation — post-narrowing (PR pdr-rtv-trigger-tighten).
#
# Tests the documentation contract — `skills/intake/SKILL.md` Step 2d-bis,
# `skills/pdr-rtv/SKILL.md`, and `protocols/skill-directory.md` /pdr-rtv row
# must specify the tightened conjunctive trigger:
#   - pdr_rtv = budget >= ${CLAUDE_PDR_RTV_BUDGET_FLOOR:-10} AND critical == true
#   - default trigger floor is 10 (NOT 7, NOT 9)
#   - flag persisted to pipeline-state/{task-id}/intake.md frontmatter
# Tests grep the source-of-truth documents (the formula text IS the spec).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  INTAKE_SKILL="$REPO_ROOT/skills/intake/SKILL.md"
  PDR_RTV_SKILL="$REPO_ROOT/skills/pdr-rtv/SKILL.md"
  SKILL_DIRECTORY="$REPO_ROOT/protocols/skill-directory.md"
  [ -f "$INTAKE_SKILL" ]
  [ -f "$PDR_RTV_SKILL" ]
  [ -f "$SKILL_DIRECTORY" ]
}

@test "intake_writes_pdr_rtv_flag_when_budget_ge_10_and_critical" {
  # Default floor 10 with env-var override AND critical-required.
  run grep -E "pdr_rtv\s*=\s*budget\s*>=\s*\\\$\{CLAUDE_PDR_RTV_BUDGET_FLOOR:-10\}\s+AND\s+critical" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
}

@test "intake_persists_pdr_rtv_to_intake_md_frontmatter" {
  # The skill must specify that pdr_rtv is written to intake.md frontmatter.
  run grep -E "pdr_rtv:\s*(true|false|\\{true\\|false\\})" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
}

@test "intake_honors_pdr_rtv_budget_floor_env_override" {
  # The env var override is documented and default-10 floor is mentioned.
  run grep -E "CLAUDE_PDR_RTV_BUDGET_FLOOR" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
  # The default-10 floor is documented (formula form OR prose form).
  run grep -E ":-10}|default.*10|default 10" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
}

@test "intake_documents_pdr_rtv_default_floor_not_7_or_9" {
  # The default floor is 10. Old budget>=7 and budget>=9 defaults must NOT
  # appear in the active formula. (Historical mentions in changelog-style
  # prose like "shifted from OR-with-floor-9" are tolerated; only the
  # active formula token `CLAUDE_PDR_RTV_BUDGET_FLOOR:-7` or `:-9` is fatal.)
  run grep -E "CLAUDE_PDR_RTV_BUDGET_FLOOR:-7" "$INTAKE_SKILL"
  [ "$status" -ne 0 ]
  run grep -E "CLAUDE_PDR_RTV_BUDGET_FLOOR:-9" "$INTAKE_SKILL"
  [ "$status" -ne 0 ]
}

@test "intake_pdr_rtv_formula_uses_AND_not_OR" {
  # Mutation guard: the formula combines two clauses with AND, not OR.
  # Positive: AND critical on formula line.
  run grep -E "pdr_rtv\s*=\s*budget\s*>=\s*\\\$\{CLAUDE_PDR_RTV_BUDGET_FLOOR:-10\}\s+AND\s+critical" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
  # Negative: `OR critical` must not appear on the active formula line.
  run grep -E "pdr_rtv\s*=\s*budget\s*>=\s*\\\$\{CLAUDE_PDR_RTV_BUDGET_FLOOR:-[0-9]+\}\s+OR\s+critical" "$INTAKE_SKILL"
  [ "$status" -ne 0 ]
}

@test "intake_pdr_rtv_formula_uses_ge_not_gt" {
  # Mutation guard: the formula uses >= (greater-or-equal), not > (greater-than).
  # The default floor is 10, and budget==10 must trigger PDR-RTV.
  run grep -E "pdr_rtv\s*=\s*budget\s*>=\s*\\\$\{CLAUDE_PDR_RTV_BUDGET_FLOOR:-10\}" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
  # Negative: bare `>` should not appear in the formula (without =).
  run grep -E "pdr_rtv\s*=\s*budget\s*>\s+\\\$" "$INTAKE_SKILL"
  [ "$status" -ne 0 ]
}

@test "intake_pdr_rtv_requires_critical_true" {
  # The critical clause MUST be explicitly required (==true), AND-joined.
  run grep -E "AND\s+critical\s*==\s*true" "$INTAKE_SKILL"
  [ "$status" -eq 0 ]
}

@test "skill_directory_pdr_rtv_row_uses_and_floor_10" {
  # The /pdr-rtv row in the skill-directory must reference the new
  # floor=10 and AND-clause trigger.
  run grep -E "/pdr-rtv.*CLAUDE_PDR_RTV_BUDGET_FLOOR:-10\}.*AND\s+critical" "$SKILL_DIRECTORY"
  [ "$status" -eq 0 ]
  # And the pdr-rtv SKILL.md trigger sentence also updated.
  run grep -E "CLAUDE_PDR_RTV_BUDGET_FLOOR:-10\}\s+AND\s+critical" "$PDR_RTV_SKILL"
  [ "$status" -eq 0 ]
}

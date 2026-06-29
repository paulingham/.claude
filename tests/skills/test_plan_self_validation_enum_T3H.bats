#!/usr/bin/env bats
# Slice B — AC B6
# Asserts skills/plan-self-validation/SKILL.md frontmatter enum lines for
# tier_initial and tier_replanned include T3H. Pins E-6 (plan-self-validation
# enum must stay in lockstep with intake and routing tables).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  PSV_SKILL="$REPO_ROOT/skills/plan-self-validation/SKILL.md"
}

@test "plan-self-validation/SKILL.md exists" {
  [ -f "$PSV_SKILL" ]
}

@test "tier_initial enum line includes T3H" {
  grep -E '^tier_initial:' "$PSV_SKILL" | grep -qE 'T3H'
}

@test "tier_replanned enum line includes T3H" {
  grep -E '^tier_replanned:' "$PSV_SKILL" | grep -qE 'T3H'
}

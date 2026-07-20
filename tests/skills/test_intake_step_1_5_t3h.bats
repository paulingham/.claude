#!/usr/bin/env bats
# GEAR MIGRATION: skills/intake/SKILL.md Step 1.5 is now a gear-READER (see
# test_intake_step_1_5.bats). The T3H_trivial_code detector concept and its
# own copy of the canonical keyword list are RETIRED — classification moved
# entirely to hooks/_lib/gear-select.sh (tested in tests/shell/test_gear_select.bats).
#
# LOCKSTEP (kept): SKILL.md still documents the canonical 17-keyword list
# informationally in Step 1.5 so operators reading intake docs understand why
# gear-select.sh escalates to PIPELINE. This test pins that the documented
# list stays lockstep with protocols/work-class-routing.md and does not drift.
#
# DELETED: the T3H_trivial_code detector-block assertions (5 conjunctive
# conditions, OpenAPI round-up rule, worked example) — no detector runs in
# skills/intake/SKILL.md anymore; those concerns moved to gear-select.sh.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  INTAKE_SKILL="$REPO_ROOT/skills/intake/SKILL.md"
}

# LOCKSTEP — canonical 17-keyword list present (informationally) in SKILL.md
@test "test_canonical_17_keyword_list_present_in_skill" {
  # WHY: pins the full canonical list; RED if any keyword is absent.
  CANONICAL='auth|token|secret|payment|session|crypto|password|billing|oauth|jwt|cors|csrf|cookie|admin|rbac|cert|signature'
  grep -qF "$CANONICAL" "$INTAKE_SKILL"
}

@test "test_skill_keyword_list_lockstep_with_routing_protocol" {
  # WHY: cross-file lockstep check — both SKILL.md and work-class-routing.md must
  # carry the identical canonical 17-keyword string (no drift between files).
  ROUTING="$REPO_ROOT/protocols/work-class-routing.md"
  CANONICAL='auth|token|secret|payment|session|crypto|password|billing|oauth|jwt|cors|csrf|cookie|admin|rbac|cert|signature'
  grep -qF "$CANONICAL" "$INTAKE_SKILL"
  grep -qF "$CANONICAL" "$ROUTING"
}

@test "test_skill_keyword_list_lockstep_with_gear_select" {
  # WHY: cross-file lockstep check — SKILL.md's informational list must match
  # the live classifier keywords in hooks/_lib/gear-select.sh (though the
  # regex there is not required to preserve alternation ordering).
  LIB="$REPO_ROOT/hooks/_lib/gear-select.sh"
  for kw in auth token secret payment session crypto password billing oauth jwt \
            cors csrf cookie admin rbac cert signature; do
    grep -qE "$kw" "$LIB" || { echo "gear-select.sh missing keyword: ${kw}"; return 1; }
  done
}

#!/usr/bin/env bats
# Slice-C detector-spec tests for skills/intake/SKILL.md
#
# C1: T3H_trivial_code detector block exists with all 5 conjunctive conditions.
# C2: Published OpenAPI contract → contract_eligible=false → round up to T4.
# C3: Motivating worked example (internal JSON shape, 1 handler, no OpenAPI) → T3H.
# LOCKSTEP: canonical 17-keyword list identical at Phase-1 detector and Phase-2
#           prose in SKILL.md; both must match work-class-routing.md (cross-file).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  INTAKE_SKILL="$REPO_ROOT/skills/intake/SKILL.md"
}

# LOCKSTEP — canonical 17-keyword list present in Phase-1 detector and Phase-2 prose
@test "test_canonical_17_keyword_list_in_skill_phase1_detector" {
  # WHY: pins the full canonical list; RED if any keyword is absent from Phase-1.
  CANONICAL='auth|token|secret|payment|session|crypto|password|billing|oauth|jwt|cors|csrf|cookie|admin|rbac|cert|signature'
  grep -qF "$CANONICAL" "$INTAKE_SKILL"
}

@test "test_skill_phase2_prose_contains_all_17_keywords" {
  # WHY: Phase-2 prose must carry the same 17 keywords to prevent drift.
  for kw in auth payment token secret crypto password session billing oauth jwt cors csrf cookie admin rbac cert signature; do
    grep -qE "User prompt contains.*${kw}|${kw}.*change-target" "$INTAKE_SKILL" || \
      { echo "SKILL.md Phase-2 prose missing keyword: ${kw}"; return 1; }
  done
}

@test "test_skill_keyword_list_lockstep_with_routing_protocol" {
  # WHY: cross-file lockstep check — both SKILL.md and work-class-routing.md must
  # carry the identical canonical 17-keyword string (no drift between files).
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  ROUTING="$REPO_ROOT/protocols/work-class-routing.md"
  CANONICAL='auth|token|secret|payment|session|crypto|password|billing|oauth|jwt|cors|csrf|cookie|admin|rbac|cert|signature'
  grep -qF "$CANONICAL" "$INTAKE_SKILL"
  grep -qF "$CANONICAL" "$ROUTING"
}

# C1 — all 5 conjunctive conditions named in the T3H_trivial_code detector block
@test "test_detector_fires_T3H_on_trivial_internal_code_change" {
  # ≤1 code file condition
  grep -qE '(≤1|<=1).*code.*file|exactly.*≤1.*predicted.*CODE.*file|≤1 predicted CODE file' "$INTAKE_SKILL"
  # ≤15 changed lines (exact, no tilde)
  grep -qE '(≤15|<=15).*changed.*lines|15 changed lines' "$INTAKE_SKILL"
  # no test file in scope
  grep -qE 'NO test file|no test file' "$INTAKE_SKILL"
  # no security keyword
  grep -qE 'auth\|token\|secret\|payment\|session\|crypto\|password\|billing\|oauth\|jwt' "$INTAKE_SKILL"
  # contract_eligible == true
  grep -qE 'contract_eligible' "$INTAKE_SKILL"
}

# C2 — published OpenAPI → T4 round-up rule documented
@test "test_detector_rounds_up_to_T4_on_public_openapi_contract" {
  grep -qE 'OpenAPI.*round.*up.*T4|OpenAPI.*T4|published.*OpenAPI.*T4|openapi\.yaml.*T4' "$INTAKE_SKILL"
}

# C3 — motivating worked example is present and names T3H as eligible
@test "test_motivating_internal_json_serialization_is_T3H" {
  # The example: internal JSON response serialization, 1 handler, no OpenAPI, ~8 lines → T3H eligible
  grep -qE 'internal.*JSON|JSON.*internal|JSON.*handler|handler.*JSON' "$INTAKE_SKILL"
  grep -qE 'T3H eligible|eligible.*T3H' "$INTAKE_SKILL"
}

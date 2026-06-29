#!/usr/bin/env bats
# Slice-C detector-spec tests for skills/intake/SKILL.md
#
# C1: T3H_trivial_code detector block exists with all 5 conjunctive conditions.
# C2: Published OpenAPI contract → contract_eligible=false → round up to T4.
# C3: Motivating worked example (internal JSON shape, 1 handler, no OpenAPI) → T3H.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  INTAKE_SKILL="$REPO_ROOT/skills/intake/SKILL.md"
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

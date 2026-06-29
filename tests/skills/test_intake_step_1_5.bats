#!/usr/bin/env bats
# Slice B — AC3 (intake Step 1.5 + task_id status line + frontmatter spec)
# Verifies skills/intake/SKILL.md contains the new Step 1.5 Fingerprint section
# between Step 1b and Step 2; that Phase 1/2 substructure is named; that
# "Phase 3 deferred — see § Phase 3 Status" is explicit; that the persistence
# clause names all 12 forensic-schema fields; that the new
# `[Intake] task_id: {task-id}` status line is present in Step 4.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  INTAKE_SKILL="$REPO_ROOT/skills/intake/SKILL.md"
}

@test "Step 1.5 section header exists" {
  grep -E '^### Step 1\.5: Fingerprint' "$INTAKE_SKILL"
}

@test "Step 1.5 sits between Step 1b and Step 2" {
  local s1b s15 s2
  s1b=$(grep -n -E '^### Step 1b' "$INTAKE_SKILL" | head -1 | cut -d: -f1)
  s15=$(grep -n -E '^### Step 1\.5:' "$INTAKE_SKILL" | head -1 | cut -d: -f1)
  s2=$(grep -n -E '^### Step 2:' "$INTAKE_SKILL" | head -1 | cut -d: -f1)
  [ -n "$s1b" ] && [ -n "$s15" ] && [ -n "$s2" ]
  [ "$s1b" -lt "$s15" ]
  [ "$s15" -lt "$s2" ]
}

@test "Step 1.5 names Phase 1 and Phase 2 substructure" {
  grep -E 'Phase 1' "$INTAKE_SKILL"
  grep -E 'Phase 2' "$INTAKE_SKILL"
}

@test "Step 1.5 explicitly defers Phase 3" {
  grep -E 'Phase 3 deferred' "$INTAKE_SKILL"
}

@test "Step 4 emits the task_id status line marker" {
  grep -E '\[Intake\] task_id:' "$INTAKE_SKILL"
}

@test "Step 1.5 persistence clause names all 12 forensic-schema fields" {
  local f
  for f in \
    tier_emitted tier_initial detector_phase detector_confidence \
    user_phrasing_signals phrasing_honoured override_token \
    safety_override_fired predicted_files fingerprint_cost_tokens \
    criticality_filtered_by_tier task_id; do
    grep -qE "\`${f}\`|${f}:" "$INTAKE_SKILL" || { echo "missing field: ${f}"; return 1; }
  done
}

@test "Step 2d tier-filter for critical at T1/T2 documented" {
  grep -E 'tier.*T1.*T2|T1.*T2.*critical|critical.*T1.*T2' "$INTAKE_SKILL"
}

@test "Step 2d-bis tier-gate for bestofn/pdr_rtv at T6" {
  grep -E 'bestofn.*T6|T6.*bestofn|pdr_rtv.*T6|T6.*pdr_rtv' "$INTAKE_SKILL"
}

@test "tier_emitted enum line includes T3H" {
  grep -E '^tier_emitted:' "$INTAKE_SKILL" | grep -qE 'T3H'
}

@test "tier_initial enum line includes T3H" {
  grep -E '^tier_initial:' "$INTAKE_SKILL" | grep -qE 'T3H'
}

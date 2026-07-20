#!/usr/bin/env bats
# Slice B — AC3 (intake Step 1.5 + task_id status line + frontmatter spec)
# GEAR MIGRATION: Step 1.5 is now a gear-READER (reads gear-<sid> state
# persisted by hooks/_lib/gear-select.sh), not a T0-T6 fingerprint detector.
# Verifies skills/intake/SKILL.md contains the Step 1.5 Gear Read section
# between Step 1b and Step 2; that the persisted-gear read pattern is named;
# that the persistence clause names all 12 forensic-schema fields; that the
# `[Intake] task_id: {task-id}` status line is present in Step 4.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  INTAKE_SKILL="$REPO_ROOT/skills/intake/SKILL.md"
}

@test "Step 1.5 section header exists" {
  grep -E '^### Step 1\.5: Gear Read' "$INTAKE_SKILL"
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

@test "Step 1.5 names the gear-<sid> state key it reads" {
  grep -E 'gear-<sid>|gear-\$\{sid\}|gear-\"\$sid\"' "$INTAKE_SKILL"
}

@test "Step 1.5 documents the missing-gear fail-safe defaults to PIPELINE" {
  grep -E 'Missing-gear fail-safe' "$INTAKE_SKILL"
  grep -E 'default to `gear: PIPELINE`|fail SAFE.*fail HEAVY' "$INTAKE_SKILL"
}

@test "Step 4 emits the task_id status line marker" {
  grep -E '\[Intake\] task_id:' "$INTAKE_SKILL"
}

@test "Step 1.5 persistence clause names all 12 forensic-schema fields" {
  local f
  for f in \
    gear_emitted gear_initial detector_phase detector_confidence \
    user_phrasing_signals phrasing_honoured override_token \
    safety_override_fired predicted_files fingerprint_cost_tokens \
    criticality_filtered_by_gear task_id; do
    grep -qE "\`${f}\`|${f}:" "$INTAKE_SKILL" || { echo "missing field: ${f}"; return 1; }
  done
}

@test "Step 2d gear-filter for critical at gear==PAIR documented" {
  grep -E 'gear.*==.*PAIR|PAIR.*critical|critical.*PAIR' "$INTAKE_SKILL"
}

@test "Step 2d-bis gear-gate for bestofn/pdr_rtv at PIPELINE" {
  grep -E 'bestofn.*PIPELINE|PIPELINE.*bestofn|pdr_rtv.*PIPELINE|PIPELINE.*pdr_rtv' "$INTAKE_SKILL"
}

@test "gear_emitted enum line includes PAIR, BUILD, PIPELINE" {
  grep -E '^gear_emitted:' "$INTAKE_SKILL" | grep -qE 'PAIR'
  grep -E '^gear_emitted:' "$INTAKE_SKILL" | grep -qE 'BUILD'
  grep -E '^gear_emitted:' "$INTAKE_SKILL" | grep -qE 'PIPELINE'
}

@test "gear_initial enum line includes PAIR, BUILD, PIPELINE" {
  grep -E '^gear_initial:' "$INTAKE_SKILL" | grep -qE 'PAIR'
  grep -E '^gear_initial:' "$INTAKE_SKILL" | grep -qE 'BUILD'
  grep -E '^gear_initial:' "$INTAKE_SKILL" | grep -qE 'PIPELINE'
}

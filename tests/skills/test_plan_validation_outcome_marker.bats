#!/usr/bin/env bats
# Slice F — AC F7 (routed from slice-e review under Iron Law 6).
# Plan: pipeline-state/plan-cache-agentic/plan.md § slice-f-shadow-mode-rollout F7.
#
# plan-self-validation MUST emit `[PlanValidationOutcome] verdict: <X>` on
# stdout after writing its state file, where <X> ∈ {PLAN_APPROVED, PLAN_HOLES,
# ROUTING_UPSHIFTED}. The slice-e audit hook (hooks/plan-cache-audit.sh)
# consumes this marker to populate `pv_outcome` in plan-cache.jsonl.
# Marker shape is exact: square brackets, single space, lowercase `verdict:`,
# uppercase enum (matches the slice-e regex `\[PlanValidationOutcome\] verdict: [A-Z_]+`).

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/../.." && pwd)"
  EMIT="$REPO_ROOT/skills/plan-self-validation/_lib/emit_outcome.sh"
  SKILL="$REPO_ROOT/skills/plan-self-validation/SKILL.md"
}

# F7 — emitter prints the canonical PLAN_APPROVED marker line on stdout.
@test "F7 emit_outcome prints PLAN_APPROVED marker (verbatim shape)" {
  [ -x "$EMIT" ]
  run "$EMIT" PLAN_APPROVED
  [ "$status" -eq 0 ]
  printf '%s\n' "$output" | grep -qE '^\[PlanValidationOutcome\] verdict: PLAN_APPROVED$'
}

# F7b — PLAN_HOLES.
@test "F7b emit_outcome prints PLAN_HOLES marker" {
  run "$EMIT" PLAN_HOLES
  [ "$status" -eq 0 ]
  printf '%s\n' "$output" | grep -qE '^\[PlanValidationOutcome\] verdict: PLAN_HOLES$'
}

# F7c — ROUTING_UPSHIFTED is also a valid PV verdict (Step 0 fast-path).
@test "F7c emit_outcome prints ROUTING_UPSHIFTED marker" {
  run "$EMIT" ROUTING_UPSHIFTED
  [ "$status" -eq 0 ]
  printf '%s\n' "$output" | grep -qE '^\[PlanValidationOutcome\] verdict: ROUTING_UPSHIFTED$'
}

# F7d — rejected verdicts return non-zero AND emit no marker line.
@test "F7d emit_outcome rejects non-canonical verdicts (no marker, non-zero)" {
  run "$EMIT" BOGUS
  [ "$status" -ne 0 ]
  ! printf '%s\n' "$output" | grep -qE '^\[PlanValidationOutcome\]'
}

# F7e — exactly one marker line is emitted (no duplicates, no preface).
@test "F7e emit_outcome emits exactly one marker line" {
  run "$EMIT" PLAN_APPROVED
  [ "$status" -eq 0 ]
  local count
  count=$(printf '%s\n' "$output" | grep -cE '^\[PlanValidationOutcome\] verdict: ')
  [ "$count" -eq 1 ]
}

# F7f — SKILL.md documents the producer contract so the architect agent
# emits the marker. Without this, the contract drifts: the helper exists but
# is never invoked from the skill body.
@test "F7f SKILL.md instructs agent to emit the marker" {
  grep -qF '[PlanValidationOutcome] verdict:' "$SKILL"
  grep -qF '_lib/emit_outcome.sh' "$SKILL"
}

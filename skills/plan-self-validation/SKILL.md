---
name: "plan-self-validation"
description: "Lightweight Plan Validation for non-critical, low-budget pipelines. Architect re-reads its own plan against a structured holes-finding rubric and returns PLAN_APPROVED or PLAN_HOLES. Used in autonomous mode when criticality is standard AND Budget < 7. Heavy challenger team is reserved for critical or Budget >= 7 plans."
verdict: PLAN_APPROVED|PLAN_HOLES|ROUTING_UPSHIFTED|PLAN_FEASIBILITY_REJECTED
model: opus
argument-hint: "Path to plan file ($state_dir/{task-id}/plan.md)"
---

# Plan Self-Validation

## What This Skill Does

Architect reviews its own plan against a structured rubric, looking for holes that would only surface during Build (missing ACs, undefined types, ambiguous edges, untested error paths, missing alternatives). One-shot, no team — the lightweight branch of Plan Validation when the heavy product-reviewer + software-engineer challenger team is not justified.

## When to Invoke

The pipeline routes here automatically (autonomous mode only) when ALL are true:

- `critical == false` (intake did not tag the task as critical)
- `Budget < 7` (Complexity Budget under the heavy-challenger threshold)
- Plan file exists at `$state_dir/{task-id}/plan.md`

When `critical == true OR Budget >= 7`, the pipeline routes to the heavy product-reviewer + software-engineer challenger team instead. See `protocols/pipeline-protocol.md` § Phase Checklist (Plan).

This skill is NOT used in interactive mode — interactive mode asks the user.

## Process

### Step 0: Re-fingerprint sanity check (MANDATORY before rubric)

Before scoring the rubric, re-check the architect plan's `## Affected Files` section against the safety-upshift floor from `protocols/work-class-routing.md` § Fingerprint. The gear read at intake happens against the user prompt; the architect's Plan reveals the actual scope. Catches the failure mode where the user says "tidy docs" but the plan touches source files.

**Steps**:

1. Read `gear_initial` from `$state_dir/{task-id}/intake.md` frontmatter (set by `/harness:intake` Step 1.5 Gear Read).
2. Read the architect plan's `## Affected Files` list.
3. **Re-apply the rules/core.md safety-upshift floor**: if any affected file matches `rules/core.md` / `protocols/atdd-procedure.md` / `protocols/verdict-catalog.md` / `hooks/*.sh` body / `auth/*` / `secrets/*` / `*crypto*` / `*.env` / test files / auth-payment-crypto keywords → upshift to `PIPELINE`. This is the HIGH-1 conservative check — it stays a hard floor regardless of the retired T0-T6 detector cascade.
4. Compute `gear_replanned` from step 3 (`PIPELINE` if the floor fired, otherwise unchanged from `gear_initial`).

**Verdict**:

- If `gear_replanned` is heavier than `gear_initial` (i.e. `gear_initial` was `PAIR`/`BUILD` and the floor upshifted to `PIPELINE`) → emit `ROUTING_UPSHIFTED`, set `routing_upshifted: true`, write the state file, halt validation. Pipeline re-dispatches downstream phases at the new gear.
- If `gear_replanned == gear_initial` → set `routing_upshifted: false`, proceed to Step 1.

**Monotonic-once invariant**: re-fingerprint upshift is **monotonic-once** per pipeline (Memory M10 / plan R3). If the state file already shows `routing_upshifted: true`, Step 0 refuses to fire again — a second upshift indicates the upstream re-dispatch failed to take effect, and the pipeline halts with operator escalation. Downshifts at this stage are not honoured.

**Status line**:

```
[PlanSelfValidation] Re-fingerprint: BUILD->PIPELINE   (upshift detected)
[PlanSelfValidation] Re-fingerprint: unchanged         (BUILD preserved)
```

### Step 1: Read the Plan

Read `$state_dir/{task-id}/plan.md` end to end. The architect spawned for this skill is the same architect role that wrote the plan, but a fresh spawn — no carry-over context. The fresh read is load-bearing.

### Step 2: Apply the Holes-Finding Rubric

For each rubric item, write a one-line verdict (`OK` / `HOLE: {what is missing}`). Be specific — vague holes are not holes.

| # | Rubric Item | Looks Like a Hole When |
|---|-------------|------------------------|
| 1 | **ACs are testable** | An AC is phrased as an aspiration ("the UI should feel snappy") rather than a measurable, falsifiable assertion |
| 2 | **All ACs have failing-test stubs** | The plan lists ACs but does not list a corresponding stub in `## Failing Test Stubs (per AC)` |
| 3 | **Types are defined at the seam** | The plan calls a function/method that has no defined input or output type, or references a domain object that is never structurally specified |
| 4 | **Edges are explicit** | Boundary cases (empty list, null, unauthorized, network failure, timeout) are not named — only the happy path is mentioned |
| 5 | **Error paths are tested** | The plan describes error handling but the test stubs do not cover any error path |
| 6 | **Obvious alternative considered** | The architect picked one approach and either (a) named the obvious alternative with a one-line rejection note, OR (b) included a full `## Alternatives Considered` table. A HOLE fires only when neither (a) nor (b) is present AND the chosen approach has a genuinely obvious alternative the rubric would expect (e.g. "use a queue" when the chosen approach is synchronous and latency is unbounded). Light-mode plans skip the full table by design — that is not a hole. |
| 7 | **Slice ordering is dependency-correct** | A composed AC (depends on another AC) is listed before the foundational AC it depends on |
| 8 | **Module boundaries respect the contract** | The plan reaches across an existing module's public port into its internals, OR proposes a new boundary without defining its `interface.{ext}` artifact |

### Step 3: Verdict

- **Inline Feasibility Finding is FEASIBILITY_REJECTED** → `PLAN_FEASIBILITY_REJECTED`. Before scoring the rubric, inspect plan.md for a line matching `FEASIBILITY: FEASIBILITY_REJECTED` (the architect's inline finding from the light-gate path). If found: surface the reject-brief to the user verbatim; write `feasibility_drift` to the state file (`architect_said: FEASIBILITY_REJECTED`, `reviewers_concluded: FEASIBILITY_REJECTED`, `overturned: false`); emit `PLAN_FEASIBILITY_REJECTED` and stop. Do NOT proceed to PLAN_APPROVED/PLAN_HOLES logic — this skill is a self-judgment only (overturn to FEASIBLE is heavy-gate only). If the inline finding says `FEASIBILITY: FEASIBLE` or is absent, proceed below.
- **Step 0 upshift detected** → `ROUTING_UPSHIFTED`. Write the upshift fields (`gear_initial`, `gear_replanned`, `routing_upshifted: true`) to `$state_dir/{task-id}/plan-validation.md` and return. The pipeline re-dispatches downstream phases at the new gear.
- **All items OK** → `PLAN_APPROVED`. Write a one-line confirmation to `$state_dir/{task-id}/plan-validation.md` and return.
- **One or more HOLE entries** → `PLAN_HOLES`. Write the hole list to `$state_dir/{task-id}/plan-validation.md` and return. The pipeline returns the plan to architect with the hole list for ONE revision pass. If holes persist after that pass, the pipeline escalates to heavy challengers (product-reviewer + software-engineer team) per `protocols/pipeline-protocol.md`.

### Step 4: Write Validation State File

Write `$state_dir/{task-id}/plan-validation.md`:

```markdown
---
task_id: {task-id}
phase: plan-validation
mode: light
verdict: PLAN_APPROVED | PLAN_HOLES | ROUTING_UPSHIFTED | PLAN_FEASIBILITY_REJECTED
gear_initial: PAIR|BUILD|PIPELINE
gear_replanned: PAIR|BUILD|PIPELINE
routing_upshifted: true|false
timestamp: {ISO 8601}
---

## Rubric Results
| # | Item | Verdict |
|---|------|---------|
| 1 | ACs are testable | OK / HOLE: {what} |
| 2 | All ACs have failing-test stubs | OK / HOLE: {what} |
| 3 | Types are defined at the seam | OK / HOLE: {what} |
| 4 | Edges are explicit | OK / HOLE: {what} |
| 5 | Error paths are tested | OK / HOLE: {what} |
| 6 | Alternatives are real | OK / HOLE: {what} |
| 7 | Slice ordering is dependency-correct | OK / HOLE: {what} |
| 8 | Module boundaries respect the contract | OK / HOLE: {what} |

## Holes (when verdict == PLAN_HOLES)
- {hole 1, with file/AC reference}
- {hole 2, ...}

## Next
{If PLAN_APPROVED: "Build phase may proceed." If PLAN_HOLES: "Architect, address holes 1, 3 and re-emit plan."}
```

## Phase Output

```
Verdict: PLAN_APPROVED | PLAN_HOLES | ROUTING_UPSHIFTED | PLAN_FEASIBILITY_REJECTED
Mode: light
Holes: {N}
Gear: {initial}->{replanned}  (when ROUTING_UPSHIFTED)
Next: Build (if APPROVED) | Architect revision (if HOLES) | Pipeline re-dispatch (if ROUTING_UPSHIFTED)
```

### Step 5: Emit the [PlanValidationOutcome] marker (MANDATORY)

After Step 4 writes the state file, the skill MUST emit one marker line on
stdout so the slice-e plan-cache audit hook (`hooks/plan-cache-audit.sh`)
can populate `pv_outcome` in `metrics/{session}/plan-cache.jsonl`. Without
this marker, the slice-g rollout-gate skill's `pv_pass_rate_on_hit` stays 0
in production and every flip-to-`on` PR is rejected.

**Invocation** (architect MUST run this as the final action of the skill,
exactly once, after Step 4):

```bash
"$CLAUDE_SKILL_DIR/plan-self-validation/_lib/emit_outcome.sh" <VERDICT>
```

where `<VERDICT>` is the same verdict written to `plan-validation.md` —
one of `PLAN_APPROVED`, `PLAN_HOLES`, `ROUTING_UPSHIFTED`, `PLAN_FEASIBILITY_REJECTED`.

**Marker shape (exact, do NOT paraphrase)**:

```
[PlanValidationOutcome] verdict: <VERDICT>
```

The slice-e regex (`hooks/plan-cache-audit.sh:30`) anchors on this exact
form: square brackets, single space, lowercase `verdict:`, uppercase enum.
Drift here breaks the consumer silently.

## Why a Skill, Not a Team

The heavy challenger team (product-reviewer + software-engineer) is the right choice when criticality or budget makes a missed flaw expensive. For low-budget standard work, the architect's own structured re-read catches the same class of holes at a fraction of the cost. The rubric is the load-bearing piece — without it, self-validation becomes "I read it again and it looked fine," which is worthless.

If the rubric is producing too many false-APPROVEDs (caught by Build-phase rework), tighten or extend it. If too many false-HOLEs (architect flagging holes that aren't really holes), simplify. Track via observation capture in the Reflect step.

$ARGUMENTS

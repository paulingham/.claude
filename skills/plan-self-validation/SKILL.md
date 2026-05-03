---
name: "plan-self-validation"
description: "Lightweight Plan Validation for non-critical, low-budget pipelines. Architect re-reads its own plan against a structured holes-finding rubric and returns PLAN_APPROVED or PLAN_HOLES. Used in autonomous mode when criticality is standard AND Budget < 7. Heavy challenger team is reserved for critical or Budget >= 7 plans."
model: opus
argument-hint: "Path to plan file (pipeline-state/{task-id}/plan.md)"
---

# Plan Self-Validation

## What This Skill Does

Architect reviews its own plan against a structured rubric, looking for holes that would only surface during Build (missing ACs, undefined types, ambiguous edges, untested error paths, missing alternatives). One-shot, no team — the lightweight branch of Plan Validation when the heavy product-reviewer + software-engineer challenger team is not justified.

## When to Invoke

The pipeline routes here automatically (autonomous mode only) when ALL are true:

- `critical == false` (intake did not tag the task as critical)
- `Budget < 7` (Complexity Budget under the heavy-challenger threshold)
- Plan file exists at `pipeline-state/{task-id}/plan.md`

When `critical == true OR Budget >= 7`, the pipeline routes to the heavy product-reviewer + software-engineer challenger team instead. See `rules/_detail/pipeline-protocol.md` § Phase Checklist (Plan).

This skill is NOT used in interactive mode — interactive mode asks the user.

## Process

### Step 1: Read the Plan

Read `pipeline-state/{task-id}/plan.md` end to end. The architect spawned for this skill is the same architect role that wrote the plan, but a fresh spawn — no carry-over context. The fresh read is load-bearing.

### Step 2: Apply the Holes-Finding Rubric

For each rubric item, write a one-line verdict (`OK` / `HOLE: {what is missing}`). Be specific — vague holes are not holes.

| # | Rubric Item | Looks Like a Hole When |
|---|-------------|------------------------|
| 1 | **ACs are testable** | An AC is phrased as an aspiration ("the UI should feel snappy") rather than a measurable, falsifiable assertion |
| 2 | **All ACs have failing-test stubs** | The plan lists ACs but does not list a corresponding stub in `## Failing Test Stubs (per AC)` |
| 3 | **Types are defined at the seam** | The plan calls a function/method that has no defined input or output type, or references a domain object that is never structurally specified |
| 4 | **Edges are explicit** | Boundary cases (empty list, null, unauthorized, network failure, timeout) are not named — only the happy path is mentioned |
| 5 | **Error paths are tested** | The plan describes error handling but the test stubs do not cover any error path |
| 6 | **Alternatives are real** | `## Alternatives Considered` exists but contains fewer than 2 genuine approaches (e.g. "Option B: don't do it" is not an alternative) |
| 7 | **Slice ordering is dependency-correct** | A composed AC (depends on another AC) is listed before the foundational AC it depends on |
| 8 | **Module boundaries respect the contract** | The plan reaches across an existing module's public port into its internals, OR proposes a new boundary without defining its `interface.{ext}` artifact |

### Step 3: Verdict

- **All items OK** → `PLAN_APPROVED`. Write a one-line confirmation to `pipeline-state/{task-id}/plan-validation.md` and return.
- **One or more HOLE entries** → `PLAN_HOLES`. Write the hole list to `pipeline-state/{task-id}/plan-validation.md` and return. The pipeline returns the plan to architect with the hole list for ONE revision pass. If holes persist after that pass, the pipeline escalates to heavy challengers (product-reviewer + software-engineer team) per `rules/_detail/pipeline-protocol.md`.

### Step 4: Write Validation State File

Write `pipeline-state/{task-id}/plan-validation.md`:

```markdown
---
task_id: {task-id}
phase: plan-validation
mode: light
verdict: PLAN_APPROVED | PLAN_HOLES
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
Verdict: PLAN_APPROVED | PLAN_HOLES
Mode: light
Holes: {N}
Next: Build (if APPROVED) | Architect revision (if HOLES)
```

## Why a Skill, Not a Team

The heavy challenger team (product-reviewer + software-engineer) is the right choice when criticality or budget makes a missed flaw expensive. For low-budget standard work, the architect's own structured re-read catches the same class of holes at a fraction of the cost. The rubric is the load-bearing piece — without it, self-validation becomes "I read it again and it looked fine," which is worthless.

If the rubric is producing too many false-APPROVEDs (caught by Build-phase rework), tighten or extend it. If too many false-HOLEs (architect flagging holes that aren't really holes), simplify. Track via observation capture in the Reflect step.

$ARGUMENTS

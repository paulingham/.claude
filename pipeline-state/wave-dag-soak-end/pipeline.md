---
task_id: wave-dag-soak-end
phase: pipeline
verdict: dormant
not_before: 2026-08-08T00:00:00Z
parent_pipeline: architect-plan-dag
soak_window_days: 90
weekly_resurface: true
classification: refactor
task_class: refactor-harness
budget: 5
critical: false
---

# WAVE DAG — Schema v2 Soak-End Cleanup

This is a placeholder anchor — DO NOT activate before `not_before` (2026-08-08).

## Purpose

90 days after `architect-plan-dag` was merged, the DUAL_PATH soak for
plan-schema v2 ends. This pipeline retires the dual-read code paths and
collapses the harness onto v2-only.

## Cleanup Gate

The cleanup pipeline must NOT proceed while any in-flight v1 plans exist.
The detection query is:

```
find pipeline-state -maxdepth 2 -name plan.md -exec grep -L 'schema_version: 2' {} \;
```

Gate is **green** when the query returns empty (zero v1 plans remaining).

## Cleanup Actions (gate-green)

1. Remove the v1-rejection branch in `hooks/_lib/plan_dag_resolver.py`
   (the `parse_plan` reader rejects v1 plans during the soak; after the
   soak, plans without `schema_version: 2` are silently invalid — the
   helper drops the dedicated v1 error path and the accompanying tests).
2. Remove the legacy multi-slice dispatch branch in
   `orchestrator/parallel-dispatch-details.md` § Multi-Slice DAG Mode
   (the v1 fallback that fires when the helper rejects the plan; v2 is
   the only supported shape after soak-end).
3. Update `agents/architect.md` § Artifact 5 to drop the "REQUIRED for
   schema_version: 2" qualifier — Artifact 5 becomes simply REQUIRED.
4. Run `/internal-eval run` against the harness regression suite; verdict
   must be `EVAL_PASSED` before merge.

## Operator Escape Hatch (gate-red)

If 2026-08-08 arrives with the cleanup gate still red (in-flight v1
plans remain), the operator has three options. SessionStart's
active-pipeline scan re-surfaces this placeholder weekly via the
`weekly_resurface: true` frontmatter flag, so the prompt does not get
buried.

1. **Extend the soak window with rationale**. Bump `not_before` to a
   later date and append a `## Extension` block to this file documenting
   why. Acceptable when the v1 plans are actively being drained and a
   short additional window will close the gate naturally.
2. **Abandon stale v1 plans**. For pipelines that are blocked or
   orphaned, mark their `pipeline.md` `verdict: abandoned` and append a
   `## Abandoned` audit entry. Cleanup proceeds once the gate query
   returns empty.
3. **Force-merge with `CLAUDE_FORCE_V1_DRAIN=1`**. Last resort: set the
   env var in the cleanup pipeline's shell to bypass the gate and treat
   any remaining v1 plans as no-ops. The helper logs each bypass to
   `metrics/{session-id}/v1-drain.jsonl` for forensic visibility.

## Status File (status.md sibling)

When SessionStart's scanner surfaces this placeholder past `not_before`,
the scanner writes/updates `pipeline-state/wave-dag-soak-end/status.md`
with the live list of in-flight v1 plan paths (one per line). Operators
read `status.md` to size the gate-red decision before invoking any of
the three options above.

## Activation

SessionStart's `_psp_find_active_pipelines` scan surfaces this file
once today's date passes `not_before`. The operator (or `/loop`) invokes
the cleanup pipeline manually — there is no auto-invocation gate.
Filtering by `not_before` is a slice-c-consumer carryforward; today's
scanner returns the file unconditionally and the operator decides
whether the date has passed.

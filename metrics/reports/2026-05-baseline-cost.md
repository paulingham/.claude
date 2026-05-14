# Baseline Cost Snapshot — 2026-05 (Model Demotion Pass)

Committed snapshot at the start of the slice-C flip (planning-agent + architect-context-recon → Haiku). Captures the pre-flip cost picture so post-flip deltas have an anchor.

## Scope

- planning-agent (long-lived, Build-phase, multi-slice only)
- code-reviewer (one spawn per Build slice + re-review rounds)
- architect-context-recon (three modes spawned in parallel before Plan)

## Data Status

No `metrics/*/cost-records.jsonl` rows are available at snapshot time — the per-spawn cost record schema lands later in the demotion pass. This file is therefore a **stub** describing the leading indicators a follow-up `/cost-report` run will need to evaluate.

## Leading Indicators

- **Leading indicator (post-flip): code-reviewer spawns at CB<6 should show Sonnet-only model selection in metrics/*/cost-records.jsonl rows.** Any Opus row for code-reviewer at CB<6 after the flip is a regression.
- **planning-agent**: every row should declare `model: haiku` post-flip. No `sonnet` rows expected — the agent is locked, never tunable up. Cross-pipeline drift here means the frontmatter was reverted somewhere.
- **architect-context-recon** (all three modes): same Haiku lock as planning-agent. Any Sonnet row is a regression.

## Verification Plan

Once `metrics/*/cost-records.jsonl` is populated:

1. `jq 'select(.agent_role == "planning-agent" and .model != "haiku")' metrics/*/cost-records.jsonl` — must be empty.
2. `jq 'select(.agent_role == "code-reviewer" and .complexity_budget < 6 and .model == "opus")' metrics/*/cost-records.jsonl` — must be empty (CB<6 cost gate working).
3. `jq 'select(.agent_role == "architect-context-recon" and .model != "haiku")' metrics/*/cost-records.jsonl` — must be empty.

## Notes

- This snapshot is committed to the slice-C branch so the post-flip `/cost-report` invocation has a diff target.
- See `protocols/cost-discipline.md` and `pipeline-state/model-demotion-pass-2026-05/plan.md` for the broader demotion pass context.

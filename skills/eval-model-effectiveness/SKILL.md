---
name: "eval-model-effectiveness"
description: "Use when user wants to Analyse accumulated pipeline observations and cost metrics to recommend per-role model downgrades (Opus → Sonnet, Sonnet → Haiku) or upgrades when outcomes are statistically indistinguishable. Advisory only — produces a markdown report, never modifies agent configs."
argument-hint: "Optional: project hash or 'global'"
---

# Eval Model Effectiveness

## What This Skill Does

Analyses pipeline observations and per-agent cost records for a project, then produces a recommendation report of where an agent role's model could be downgraded (Opus → Sonnet, Sonnet → Haiku) or upgraded, based on success-rate parity and cost-per-success delta.

**Advisory only.** The skill writes a markdown report. It does NOT modify agent definitions and does NOT route models at runtime. A human operator decides whether to act on a recommendation by editing the affected agent's `.md` frontmatter. This operationalises the "Model self-tuning" protocol in CLAUDE.md and `orchestrator/agent-orchestration.md` § Instinct Injection; it does NOT replace that protocol.

## When to Invoke

- Manually via `/eval-model-effectiveness` whenever you want a fresh recommendation report.
- Automatically from the Reflect step when `observations_since_learn` is a non-zero multiple of 20. See `rules/reflection-protocol.md` § 6b-bis.

## Inputs

| Source | Path | Required fields |
|---|---|---|
| Observations | `~/.claude/learning/{project-hash}/observations.jsonl` | `record_type=="pipeline"`, `pipeline_id`, `classification`, `phases`, `rework` |
| Costs | `~/.claude/metrics/costs.jsonl` | `pipeline_id` + `agent_role` + `model` + `total_cost_usd` |
| Traces (optional) | `~/.claude/metrics/{session}/trace/` | Only used if present — enriches agent→model attribution when cost records lack `agent_role` |

Join strategy: costs.jsonl → observations.jsonl via `pipeline_id`. If a pipeline-shaped observation is missing required fields, fail fast with `SCHEMA_ERROR`; do NOT silently skip cells.

## Analysis

For each `(agent_role, task_classification)` cell:

1. Group cost records by `model` (tier-normalised).
2. For each `(role, model, classification)` subcell, join to its pipeline observations and compute:
   - **clean_first_pass_pct**: fraction of pipelines where `review.rounds <= 1`
   - **rework_rate**: fraction where `rework == true`
   - **avg_review_rounds**: mean of `review.rounds` (floor 1)
   - **success_rate** = `clean_first_pass_pct * 0.6 + (1 - rework_rate) * 0.3 + (MAX_REVIEW_ROUNDS_OBS / max(avg_review_rounds, 1)) * 0.1` where `MAX_REVIEW_ROUNDS_OBS = 2` (see `rules/pipeline-protocol.md` § Review Rules).
   - **cost_per_success**: `sum(total_cost_usd) / max(successes, 1)` where successful = `rework == false` AND `review.rounds <= 2`.
3. **Confidence gate**: require ≥10 observations per `(role, model, classification)` subcell. Below threshold → tagged `INSUFFICIENT_DATA`, not used for recommendations.

## Recommendation Rules

- **Downgrade candidate**: for a given `(role, classification)`, if there exists a cheaper-tier model with:
  - `cheaper.success_rate >= expensive.success_rate - 0.03` AND
  - `cheaper.cost_per_success < 0.6 * expensive.cost_per_success`
  - Both subcells must pass the confidence gate.
- **Upgrade candidate** (rare): `current.success_rate < 0.70` AND observation count ≥ 15 → recommend promoting to next-tier model.
- **Hard lockout**: `architect` and `security-engineer` are never recommended for change (design + security decisions require highest capability; see CLAUDE.md § Model self-tuning).
- Tier order (cheap → expensive): `haiku < sonnet < opus`.

## Invocation

```bash
python3 ~/.claude/skills/eval-model-effectiveness/analyze.py [--project-hash <hash>] [--out <path>]
```

Defaults to the current project's hash via `_project_hash --fallback "local"`. Writes the report to `~/.claude/learning/{project-hash}/model-recommendations.md` unless `--out` overrides.

## Output Report

File: `~/.claude/learning/{project-hash}/model-recommendations.md`

Sections:

- `== Summary ==` — one line per `(role, classification)` cell with one of: `DOWNGRADE <from> → <to>`, `UPGRADE <from> → <to>`, `NO CHANGE`, `INSUFFICIENT_DATA (n obs, need 10)`, `LOCKED`.
- `== Evidence ==` — per non-locked cell: observation count, success rate per model, cost/success per model, cost delta, confidence flag.
- `== How to apply ==` — instructions for a human operator to edit the agent definition file frontmatter. The orchestrator does NOT auto-apply.

## Safeguards (IRON LAW)

- Does NOT modify any agent `.md` file.
- Does NOT change the default model for anything.
- Does NOT emit recommendations for `architect` or `security-engineer`.
- Fails fast on schema drift — does NOT silently skip cells.

## Phase Output

```
Verdict: RECOMMENDATIONS_READY | INSUFFICIENT_DATA | NO_CHANGE
Next: Review the generated report; apply recommendations manually if desired
Artifacts: ~/.claude/learning/{project-hash}/model-recommendations.md
```
$ARGUMENTS

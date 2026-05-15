---
task_id: harness-opus-4-5-migration
phase: plan
verdict: in_progress
timestamp: 2026-05-15T00:00:00Z
scale: medium
branch: refactor/harness-opus-4-5-migration
critical: false
task_class: refactor
bestofn: false
pdr_rtv: false
tier_emitted: T5
complexity_budget_user_declared: 6
complexity_budget_derived: 10
mode: autonomous
multi_repo: false
---

# Pipeline: Harness Opus 4.5 Migration + Effort Param + Caching Audit

Started: 2026-05-15
Classification: refactor
Tier: T5 (standard pipeline)
Mode: autonomous (CLAUDE_PIPELINE_MODE=autonomous)

## Slices (operator-provided, multi-slice Build)

| Slice | Title | Scope |
|---|---|---|
| A | Model binding migration | `agents/*.md`, `skills/**/SKILL.md`, `CLAUDE.md`, `protocols/thinking-defaults.md`, `orchestrator/*.md`, `hooks/_lib/*.py`, `hooks/cost-feed.sh`, `skills/internal-eval/score/**`, `skills/best-of-n/config.json` |
| B | `effort` parameter | `hooks/pre-agent-thinking.sh`, agent frontmatter (`code-reviewer`, `security-engineer`, `architect` default `high`), metrics schema doc |
| C | Prompt-caching audit | Inline `cache_control {type: ephemeral, ttl: 1h}` after CLAUDE.md + agent prelude; verify min cacheable ≥4096 tokens; Agent SDK `enablePromptCaching: true` where applicable |

## Phases
- Plan: completed — PLAN_DRAFTED r2
- Plan Validation: completed — PLAN_APPROVED (round 2; both challengers APPROVE)
- Build (slice A): in_progress
- Build (slice B): pending
- Build (slice C): pending
- Security Review: pending
- Final Gate: pending
- Reflect-write: pending
- Ship: pending
- Reflect: pending

## Intake Discussion

Exploration gate fired (Ambiguity=2) but AskUserQuestion blocked by autonomous-mode hook. Operator-noted risks logged at `pipeline-state/harness-opus-4-5-migration/intake.md` § Operator-noted Risks. Architect must address all four before authoring patches.

## Key Files

To be enumerated by architect-context-recon (Stage 1 of Plan).

## Re-routes

None.

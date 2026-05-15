---
task_id: harness-opus-4-5-migration
classification: refactor
tier_emitted: T5
tier_initial: T4
detector_phase: rules
detector_confidence: high
user_phrasing_signals: ["migrate", "audit", "add support"]
phrasing_honoured: true
override_token: null
safety_override_fired: true
predicted_files:
  - agents/*.md
  - skills/**/SKILL.md
  - skills/internal-eval/score/**
  - skills/best-of-n/config.json
  - CLAUDE.md
  - protocols/thinking-defaults.md
  - protocols/autonomous-intelligence.md
  - protocols/advisor-mode.md
  - orchestrator/agent-orchestration.md
  - hooks/pre-agent-thinking.sh
  - hooks/cost-feed.sh
  - hooks/_lib/executor_resolver.py
  - hooks/_lib/cost_estimator.py
fingerprint_cost_tokens: 0
criticality_filtered_by_tier: false
critical: false
bestofn: false
pdr_rtv: false
multi_repo: false
task_class: refactor
contracts_touched:
  - agent frontmatter `model:` field across all agents (public surface for orchestrator dispatch)
  - hook injection schema in metrics/{session}/hook-injections.jsonl (added `effort` field)
  - Anthropic API beta header `effort-2025-11-24`
  - cache_control breakpoint format (inline `{type: ephemeral, ttl: 1h}`)
  - Agent SDK `enablePromptCaching` config flag (if used)
complexity_budget:
  user_declared: 6
  derived: 11
  scope: 3
  ambiguity: 2
  context: 2
  novelty: 2
  coordination: 2
  routing_budget: 10
---

# Intake: Harness Opus 4.5 Migration + Effort Param + Caching Audit

## Classification

**Refactor** — three slices touching agent/skill model bindings, hook code, and prompt-caching infrastructure. Not a feature (no new AC), not a bug fix (no failing behavior).

## Fingerprint

- **Phase 1**: Mixed transformation (model-string rename + hook body change + caching breakpoint design). Not T3 mechanical (slice 2 + 3 are not uniform replacements).
- **Phase 2 safety override**: `hooks/pre-agent-thinking.sh` body change → T4+ floor. No Iron-Law surface touched (`rules/core.md`, `protocols/atdd-procedure.md`, `rules/verdict-catalog.md` unaffected) → stays at T5, not T6.
- **Verdict**: T5 (standard feature/refactor pipeline).

## Complexity Budget

| Dimension | Score | Rationale |
|---|---|---|
| Scope | 3 | 25+ files touched across agents/, skills/, protocols/, orchestrator/, hooks/ |
| Ambiguity | 2 | Cache breakpoint design and Agent SDK integration require interpretation |
| Context | 2 | Cross-module: agent contracts + hook code + caching infra |
| Novelty | 2 | Partial precedent — prior 4.6→4.7 migration exists in commit history |
| Coordination | 2 | Three orthogonal concerns: model binding, effort param, caching |
| **Total** | **11** | User declared 6; derived 11 used for routing-shape safety (multi-slice Build dispatch) |

User-declared `Critical: false` and `Best-of-N: no` honored as-is.

## Multi-repo

No. Self-modification of `~/.claude/` harness only.

## Criticality

`standard`. Operator explicit. Touches harness self-config but no payment/auth/security keywords in change-target context.

## Best-of-N / PDR-RTV

Both disabled. User explicit override on BoN. PDR-RTV gate requires `critical=true AND budget>=10` — fails (critical=false).

## Contracts Touched

- **Agent frontmatter `model:` field** — public contract read by orchestrator at every Agent spawn. Affects all 11 agents.
- **Hook injection schema** — `metrics/{session}/hook-injections.jsonl` schema gains `effort` field (additive).
- **Anthropic API beta header** — `effort-2025-11-24` becomes a required header on tunable-effort spawns.
- **cache_control breakpoint** — inline `{type: ephemeral, ttl: 1h}` after CLAUDE.md + agent prelude (new caching contract).
- **Agent SDK `enablePromptCaching`** — config flag wherever SDK is consumed (must enumerate during Plan).

## Operator-noted Risks (architect must address at Plan phase)

1. **Model direction**: target `claude-opus-4-5` is two generations older than current `claude-opus-4-7` (per CLAUDE.md "Default Opus model" and env-declared current model). Architect MUST verify the public model ID at `anthropic.com/news/claude-opus-4-5` is still GA-available in the API before authoring the migration patch. If retired or rebranded, halt slice 1 and surface to operator.
2. **Adaptive-thinking loss**: Opus 4.7 deprecated manual `budget_tokens` in favor of adaptive thinking. Downgrading to 4.5 reinstates manual `effort` control but loses 4.7's adaptive allocation. Slice 2's `effort=medium` default is the explicit replacement.
3. **Cache regression risk**: The May 8 2026 subagent-summary cache fix is Opus-4.7-specific. Slice 3 must re-validate that the inline `cache_control` breakpoint achieves the same ≥0.7 cache-hit ratio on 4.5.
4. **Small-agent consolidation**: Slice 3 AC requires min cacheable prompt ≥4096 tokens. Smaller agents (e.g., `planning-agent`, `sandbox-verify-engineer`) may fall below threshold individually. Architect should plan a shared protocol prelude consolidation OR document which agents intentionally skip caching.

## Slices (operator-provided)

1. **Model binding migration** — `opus-4-7` → `opus-4-5` across configs; verify model ID externally; preserve historical postmortem notes; pass verdict-catalog audit.
2. **`effort` parameter support** — default `medium`, promote to `high` via `critical=true OR budget>=N` gate in `hooks/pre-agent-thinking.sh`; emit decisions to `hook-injections.jsonl`; `code-reviewer` + `security-engineer` + `architect` default `high`.
3. **Prompt-caching audit** — inline `cache_control {type: ephemeral, ttl: 1h}` after global CLAUDE.md + agent prelude; verify min cacheable ≥4096 tokens; enable Agent SDK `enablePromptCaching`; target cache-read ratio ≥0.7.

## Pre-flight

- CLAUDE.md: present (this repo IS the harness)
- In-progress pipeline: none for this task (other active pipelines noted in session-start are unrelated)
- Feature branch: orchestrator must create `refactor/harness-opus-4-5-migration` before Build (HEAD stays on main per Iron Law 4)
- Working tree: dirty (existing `pipeline-state/` and `db/codebase-map/` untracked) — does not block; operator's pre-existing state
- Baseline tests: harness-audit + verdict-consistency must run green before Plan signoff

## Routing

```
[Intake] task_id: harness-opus-4-5-migration
[Intake] Classification: refactor
[Intake] Tier: T5 (reason: rules; phase: 2; confidence: high)
[Intake] Complexity: medium-large (user-declared 6, derived 11; routing at 10)
[Intake] Criticality: standard
[Intake] Best-of-N: disabled
[Intake] PDR-RTV: disabled
[Intake] Multi-repo: no
[Intake] Contracts Touched: 5 items (function-sigs=0, schemas=2, db=0, invariants=0, config-contracts=3)
[Intake] Entry skill: /pipeline (multi-slice Build at budget 10)
[Intake] Pipeline phases: Plan → Plan Validation → Build (3 slices, cherry-picked) → Security Review → Final Gate → Ship → Reflect
```

## Verdict

ROUTED → /pipeline

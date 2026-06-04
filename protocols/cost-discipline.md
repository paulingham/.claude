# Cost Discipline

Detail prose for the harness cost-discipline posture — what the subagent-summary cache fix delivers, why preamble cache stability is load-bearing, and where the per-spawn measurement surface lives. CLAUDE.md keeps only a pointer.

## Subagent-Summary Cache Fix (May 8 2026)

The May 8 2026 subagent-summary cache fix delivers roughly ~3× `cache_creation` token reduction per subagent dispatch — **only when preambles are cache-stable** across spawns.

Preamble cache stability depends on:

- Stable instinct-injection ordering (deterministic sort by `confidence` DESC, secondary by `id` ASC — see `protocols/autonomous-intelligence.md` § Instinct Injection selection algorithm).
- Stable session-memory file contents across spawns within the same phase.
- Consistent agent-definition frontmatter (no drift in `tools:`, `model:`, `executor:`, `advisor:`, `instinct_categories:`).

Drift in any of these voids the cache-creation savings and silently doubles per-spawn cost. The cost is observable post-hoc via the per-session JSONL records (see below) — it does NOT throw an error at spawn time.

## Prompt-Caching Breakpoint Work

The harness now ships explicit `cache_control` breakpoint resolution at the PreToolUse:Agent hook layer — `hooks/cache-breakpoint-injector.sh` resolves the `rules-core-tail` anchor segment hash and TTL policy, and `skills/cache-audit/SKILL.md` aggregates measured cache token reads from `metrics/{session}/cache.jsonl` into a project-wide read-ratio report.

The hook ships **advisory/log-only at v2.1.140**: it computes the resolved anchor positions and emits one JSONL record per spawn to `metrics/{session}/cache-injections.jsonl`, but does NOT mutate `tool_input.prompt`. The flip surface for enforcement is the single line at `cache-breakpoint-injector.sh:28-29` — mirroring `pre-agent-thinking.sh:28-29` — which will swap from `log-injection.sh` to a `modified_tool_input` stdout emit once the Agent input schema exposes that field.

ProjectDiscovery reports a ~70% cache read ratio with multi-anchor enforced caching across their full preamble surface. The harness targets `READ_RATIO_TARGET = 0.60` — one decimal below their measured ratio, intentionally conservative because the harness ships only one of four anchors (`rules-core-tail`) and only at advisory level until two upstream dependencies land.

**Two upstream dependencies must land for the surviving `rules-core-tail` anchor to produce real cache reads**:

1. **Schema dependency**: `modified_tool_input` exposed on the Agent tool input schema (Claude Code release). The hook's flip surface (`cache-breakpoint-injector.sh:28-29` mirroring `pre-agent-thinking.sh:28-29`) handles this side.
2. **Splice dependency**: orchestrator-side splice of `rules/core.md` body into `tool_input.prompt`. Per `orchestrator/agent-orchestration.md:308-313`, only instincts / session-memory / scratchpad are body-spliced today — `rules/core.md` is referenced via in-body prose, not body-spliced. Tracked as follow-up ticket `prompt-caching-rules-core-splice`.

The other three anchors are deferred at the harness layer with explicit follow-up tickets:

- `persona-marker-deferred` → `prompt-caching-persona-marker`
- `protocol-splice-not-implemented` → `prompt-caching-protocol-splice`
- `outside-hook-surface-v2.1.140` → tool-result-tail anchor; Anthropic API-client-level concern, no harness surface at v2.1.140.

Hook fires on `tool_name == "Agent"` PreToolUse events only. Skill invocations and other tool spawns are out of scope; the May 8 2026 subagent-summary cache fix already covers Skill-invocation cache reads via the orthogonal SubagentStop tap.

When the breakpoint work fully lands (schema flip + splice landing), drift in upstream contributors will void specific cached segments (small blast radius) rather than the entire preamble (full re-creation).

## Per-Spawn Measurement Surface

- `skills/cost-report/SKILL.md` — the cost-tracking surface; aggregates per-session tool-timings into a project-wide spend report. Advisory only — writes a markdown report, never modifies configs.
- `hooks/_lib/cost_estimator.py` — per-spawn token accounting library; called by the cost-emission hook on every spawn.
- `metrics/{session}/*.jsonl` — per-session records of empirical measurements (cache hit/miss ratios, cache_creation/cache_read tokens, input/output tokens by role).
- `hooks/cache-breakpoint-injector.sh` + `skills/cache-audit/SKILL.md` — the prompt-cache breakpoint surface; the hook emits per-spawn anchor decisions (`metrics/{session}/cache-injections.jsonl`) and `cost-feed.sh` emits per-spawn token reads (`metrics/{session}/cache.jsonl`). The skill aggregates both into the read-ratio report.

## Slice C ESCALATION — SDK flag (2026-05-15)

SDK flag — consumer outside repo. The `enablePromptCaching: true` annotation on the Agent SDK is the runtime-API consumer that signals cache_control breakpoint enforcement to Anthropic's API. The harness has zero SDK call sites in tree (per recon D3.2 of `$state_dir/harness-opus-4-5-migration/architect-context.md`); the surface lives in the Claude Code binary / Agent SDK runtime, which is outside this repository.

The in-tree wire emission shipped 2026-05-15 as part of Slice C: `hooks/_lib/resolve-cache-breakpoints.py` emits `cache_flag: true` in the resolved payload, and `hooks/cache-breakpoint-injector.sh` writes that token into `metrics/{session}/cache-injections.jsonl` via `log-injection.sh`. When the Agent SDK consumer lands, the wire-emission token is the signal it consults; until then the token is observable-only.

## See Also

- `skills/cost-report/SKILL.md` — `/harness:cost-report` skill invocation contract.
- `skills/cache-audit/SKILL.md` — `/harness:cache-audit` skill invocation contract (prompt-cache read-ratio reporting).
- `skills/eval-model-effectiveness/SKILL.md` — model-efficiency analysis built on top of the cost-discipline records.

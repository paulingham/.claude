# Cost Discipline

Detail prose for the harness cost-discipline posture — what the subagent-summary cache fix delivers, why preamble cache stability is load-bearing, and where the per-spawn measurement surface lives. CLAUDE.md keeps only a pointer.

## Subagent-Summary Cache Fix (May 8 2026)

The May 8 2026 subagent-summary cache fix delivers roughly ~3× `cache_creation` token reduction per subagent dispatch — **only when preambles are cache-stable** across spawns.

Preamble cache stability depends on:

- Stable instinct-injection ordering (deterministic sort by `confidence` DESC, secondary by `id` ASC — see `protocols/autonomous-intelligence.md` § Instinct Injection selection algorithm).
- Stable session-memory file contents across spawns within the same phase.
- Consistent agent-definition frontmatter (no drift in `tools:`, `model:`, `executor:`, `advisor:`, `instinct_categories:`).

Drift in any of these voids the cache-creation savings and silently doubles per-spawn cost. The cost is observable post-hoc via the per-session JSONL records (see below) — it does NOT throw an error at spawn time.

## Prompt-Caching Breakpoint Work (Upcoming)

The current cache-stability invariant is **emergent** — it depends on every upstream contributor (instinct loader, session-memory writer, agent-definition author) producing byte-stable output. The upcoming prompt-caching breakpoint work will add explicit `cache_control` headers around the orchestrator → subagent prompt preamble surface to make cache-stability a **load-bearing invariant** rather than an emergent property.

When the breakpoint work lands, drift in upstream contributors will void specific cached segments (small blast radius) rather than the entire preamble (full re-creation).

## Per-Spawn Measurement Surface

- `skills/cost-report/SKILL.md` — the cost-tracking surface; aggregates per-session tool-timings into a project-wide spend report. Advisory only — writes a markdown report, never modifies configs.
- `hooks/_lib/cost_estimator.py` — per-spawn token accounting library; called by the cost-emission hook on every spawn.
- `metrics/{session}/*.jsonl` — per-session records of empirical measurements (cache hit/miss ratios, cache_creation/cache_read tokens, input/output tokens by role).

## See Also

- `skills/cost-report/SKILL.md` — `/cost-report` skill invocation contract.
- `skills/eval-model-effectiveness/SKILL.md` — model-efficiency analysis built on top of the cost-discipline records.

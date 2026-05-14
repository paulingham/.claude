# Skill Directory

Canonical catalog of every user-invocable skill in `skills/` plus the deferred forcing-function-gated skills under `skills/_deferred/`. CLAUDE.md keeps only a pointer here; the table below is the source of truth.

Verdict semantics for every entry below are defined in `rules/verdict-catalog.md` — the audit step `/harness-audit` asserts catalog/skill-frontmatter agreement in both directions.

## Active Skills

| Skill | When to Invoke | Verdict |
|-------|----------------|---------|
| `/intake` | **Entry point** — first skill for any user request; emits Step 1.5 fingerprint (tier T0..T6) alongside criticality/budget | ROUTED |
| `/pipeline` | **Conductor** — drives all phases in sequence | PIPELINE_COMPLETE |
| `/epic-breakdown` | Decomposing epics into stories | STORIES_READY |
| `/estimation` | Sizing stories with Complexity Budget | ESTIMATED |
| `/story-writing` | Writing individual user stories | STORY_READY |
| `/build-implementation` | Build phase: incremental TDD + shape checks (default). When intake sets `bestofn: true` (critical, OR `[best-of-n]` user override), the pipeline dispatches Build as a Best-of-N Team variant — see `orchestrator/parallel-dispatch-details.md` § Best-of-N Build Team Dispatch | BUILD_COMPLETE |
| `/pdr-rtv` | Build dispatch variant — Parallel-Diverse-Refine + Recursive-Tournament-Verification (arXiv:2604.16529). When intake sets `pdr_rtv: true` (`budget >= ${CLAUDE_PDR_RTV_BUDGET_FLOOR:-9} OR critical`), the pipeline dispatches Build as a PDR-RTV Team variant — T=2 iterations of N parallel rollouts, summary-based refinement, and pairwise tournament selection. Strictly stronger than Best-of-N when both fire. Tunable: No. See `orchestrator/parallel-dispatch-details.md` § PDR-RTV Build Team Dispatch | PDR_WINNER_SELECTED / PDR_NO_CONSENSUS |
| `/refactor` | Build phase: safe refactoring workflow | REFACTOR_COMPLETE |
| `/bug-fix` | Build phase: root cause analysis + TDD fix | BUG_FIXED |
| `/code-review` | Review phase: SOLID/DRY/quality audit | APPROVE / CHANGES_REQUESTED |
| `/security-review` | Review phase: OWASP/secrets/auth (parallel) | APPROVE / CHANGES_REQUESTED |
| `/verify` | Verify phase: contract + smoke + mutation | VERIFIED / UNVERIFIED |
| `/qa-test-strategy` | Test phase: coverage analysis + gap filling | COVERED / GAPS_FOUND |
| `/product-acceptance` | Accept phase: AC validation + UX | APPROVED / REJECTED |
| `/patch-critique` | Final Gate: critic step scoring patch by test results + diff (NOT SOLID — that is `/code-review`'s job). Inspired by SWE-bench top scaffolds | PATCH_APPROVED / PATCH_REJECTED |
| `/pr-creation` | Ship phase: PR creation with narrative | PR_CREATED / PR_BLOCKED |
| `/tech-spike` | Time-boxed technical research | SPIKE_COMPLETE |
| `/project-setup` | Scaffolding project-level CLAUDE.md | PROJECT_SETUP_COMPLETE |
| `/pipeline-resume` | Resume interrupted pipeline from state files | RESUMED |
| `/plan-self-validation` | Lightweight Plan Validation: architect re-reads its own plan against a structured holes-finding rubric. Used when `critical == false AND Budget < 7`; runs re-fingerprint sanity check on architect plan | PLAN_APPROVED / PLAN_HOLES / ROUTING_UPSHIFTED |
| `/harness-config` | Modify hooks, settings.json, non-.md config | CONFIG_APPLIED |
| `/deploy` | CD phase: staging/production deploy with rollback | DEPLOYED / ROLLED_BACK |
| `/infra-scaffold` | Generate Dockerfile, docker-compose, CI/CD, health endpoints | INFRA_SCAFFOLDED |
| `/api-scaffold` | Generate API endpoints, validation, pagination, rate limiting | API_SCAFFOLDED |
| `/db-migration` | Schema changes, zero-downtime migrations, reversibility | MIGRATION_COMPLETE |
| `/observability-setup` | Logging, metrics, tracing, alerting, dashboards | OBSERVABILITY_CONFIGURED |
| `/web-frontend-patterns` | React/Next.js patterns, state, a11y, performance, caching | PATTERNS_APPLIED |
| `/deployment-verification` | Post-deploy health checks, smoke tests, auto-rollback | DEPLOYMENT_VERIFIED |
| `/load-test` | Performance testing: load, stress, baselines, SLA verification | PERFORMANCE_VERIFIED |
| `/module-extraction` | Extract a bounded context into an in-process module with an explicit port (same repo, no forcing function) | BOUNDARY_READY / MODULE_EXTRACTED / EXTRACTION_BLOCKED / WRONG_SKILL |
| `/debug` | Persistent debug state for complex, multi-session bugs | DEBUG_RESOLVED |
| `/debug-trace` | Toggle prompt tracing for the current session (`on` / `off`) | TRACE_TOGGLED |
| `/forensics` | Post-incident pipeline investigation | CLEAN / ANOMALIES_FOUND |
| `/workstream` | Manage isolated workstreams for parallel development | WORKSTREAM_CREATED |
| `/batch-pipeline` | Pre-planned batch work (waves, bulk fixes) — lightweight pipeline with state tracking | BATCH_COMPLETE |
| `/polish` | Mechanical cleanup between Build and Review (Haiku) | POLISHED |
| `/design-qc` | Visual QA screenshots for product acceptance | SCREENSHOTS_CAPTURED |
| `/learn` | Analyze observations, extract instincts (learned patterns) | LEARNED |
| `/health-scan` | Proactive codebase health: security, deps, coverage, tech debt | HEALTHY / CRITICAL_ISSUES |
| `/eval-model-effectiveness` | Advisory analysis of agent model efficiency from observations + costs | RECOMMENDATIONS_READY |
| `/internal-eval` | Eval phase: suite execution, baseline capture, regression diff | EVAL_PASSED / EVAL_FAILED / EVAL_BASELINE_CAPTURED / INSUFFICIENT_CASES |
| `/greenfield-scaffold` | Full project bootstrap from scratch: discovery, tech stack, UI architecture, framework init, DevX, design, infra, seed data | GREENFIELD_SCAFFOLD_COMPLETE |
| `/creative-direction` | Pre-build design thinking: brand brief → fonts, palette, layout, interaction paradigm | CREATIVE_DIRECTION_COMPLETE |
| `/design-system-init` | Generate design tokens, primitives, dark mode for a project | DESIGN_SYSTEM_READY |
| `/tool-synthesis` | Build phase: author a one-shot scratch tool inside the worktree (codebase-specific search, AST query, custom lint) when standard tools are insufficient. Tool lives in `.claude-scratch-tools/`, never merged. Inspired by Live-SWE-agent (arXiv 2511.13646) | TOOL_SYNTHESISED / TOOL_UNNECESSARY |
| `/property-based-test` | Build phase: author Tier 1.5 PBTs for changed-line public functions with typed signatures (auto-invoked from /build-implementation Step 1d). Time-box 60s/function. Frozen counterexamples freeze inline as Tier 1 regressions using harness-native syntax. Inspired by arXiv 2510.09907 | PBT_AUTHORED / PBT_SKIPPED / PBT_BLOCKED |
| `/spec-blind-validate` | Final Gate: 5th teammate that authors black-box behavioural tests from ACs only, no source — never reads `src/` internals. Three PreToolUse hooks (read-guard / write-guard / Bash content-leak guard) enforce the spec-blind property. Catches the SWE-Bench-Pro-vs-Verified failure mode where build-time tests codify the same misconceptions as production code. Inspired by SWE-Bench Pro | SPEC_BLIND_VALIDATED / SPEC_BLIND_FAILED / SPEC_BLIND_INSUFFICIENT_SURFACE / SPEC_BLIND_BLOCKED |

## Deferred (forcing-function required)

These skills live under `skills/_deferred/` and are invoked only when a forcing function from `protocols/module-boundaries-protocol.md` is named (service / multi-repo work) or a domain-specific channel is in scope (voice). The pipeline routes automatically — you do not invoke them directly. `/microservices-scaffold` enforces the FF gate at its Step 0.

| Skill | When to Invoke | Verdict |
|-------|----------------|---------|
| `/service-extraction` | Extract module to own repo (FF required) | SERVICE_EXTRACTED |
| `/microservices-scaffold` | New microservice (FF required; Step 0 gate) | SERVICE_SCAFFOLDED / WRONG_SKILL |
| `/cross-service-pipeline` | Cross-repo contract + deploy coordination | CROSS_SERVICE_VERIFIED |
| `/bff-scaffold` | Channel-specific BFF layer | BFF_SCAFFOLDED |
| `/voice-scaffold` | Scaffold voice skill/action (Alexa, Google, Twilio IVR) | VOICE_SCAFFOLDED |

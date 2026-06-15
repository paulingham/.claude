# Skill Directory

Canonical catalog of every user-invocable skill in `skills/` plus the deferred forcing-function-gated skills under `skills/_deferred/`. CLAUDE.md keeps only a pointer here; the table below is the source of truth.

Verdict semantics for every entry below are defined in `protocols/verdict-catalog.md` — the audit step `/harness:harness-audit` asserts catalog/skill-frontmatter agreement in both directions.

## Active Skills

| Skill | When to Invoke | Verdict |
|-------|----------------|---------|
| `/harness:intake` | **Entry point** — first skill for any user request; emits Step 1.5 fingerprint (tier T0..T6) alongside criticality/budget | ROUTED |
| `/harness:pipeline` | **Conductor** — drives all phases in sequence | PIPELINE_COMPLETE |
| `/harness:epic-breakdown` | Decomposing epics into stories | STORIES_READY |
| `/harness:estimation` | Sizing stories with Complexity Budget | ESTIMATED |
| `/harness:story-writing` | Writing individual user stories | STORY_READY |
| `/harness:build-implementation` | Build phase: incremental TDD + shape checks (default). When intake sets `bestofn: true` (critical, OR `[best-of-n]` user override), the pipeline dispatches Build as a Best-of-N Team variant — see `orchestrator/parallel-dispatch-details.md` § Best-of-N Build Team Dispatch | BUILD_COMPLETE |
| `/harness:pdr-rtv` | Build dispatch variant — Parallel-Diverse-Refine + Recursive-Tournament-Verification (arXiv:2604.16529). When intake sets `pdr_rtv: true` (`budget >= ${CLAUDE_PDR_RTV_BUDGET_FLOOR:-10} AND critical == true`), the pipeline dispatches Build as a PDR-RTV Team variant — T=2 iterations of N parallel rollouts, summary-based refinement, and pairwise tournament selection. Strictly stronger than Best-of-N when both fire. Tunable: No. See `orchestrator/parallel-dispatch-details.md` § PDR-RTV Build Team Dispatch | PDR_WINNER_SELECTED / PDR_NO_CONSENSUS |
| `/harness:refactor` | Build phase: safe refactoring workflow | REFACTOR_COMPLETE |
| `/harness:bug-fix` | Build phase: root cause analysis + TDD fix | BUG_FIXED |
| `/harness:code-review` | Review phase: SOLID/DRY/quality audit | APPROVE / CHANGES_REQUESTED |
| `/harness:security-review` | Review phase: OWASP/secrets/auth (parallel) | APPROVE / CHANGES_REQUESTED |
| `/harness:verify` | Verify phase: contract + smoke + mutation | VERIFIED / UNVERIFIED |
| `/harness:qa-test-strategy` | Test phase: coverage analysis + gap filling | COVERED / GAPS_FOUND |
| `/harness:product-acceptance` | Accept phase: AC validation + UX | APPROVED / REJECTED |
| `/harness:patch-critique` | Final Gate: critic step scoring patch by test results + diff (NOT SOLID — that is `/harness:code-review`'s job). Inspired by SWE-bench top scaffolds | PATCH_APPROVED / PATCH_REJECTED |
| `/harness:pr-creation` | Ship phase: PR creation with narrative | PR_CREATED / PR_BLOCKED |
| `/harness:tech-spike` | Time-boxed technical research | SPIKE_COMPLETE |
| `/harness:project-setup` | Scaffolding project-level CLAUDE.md | PROJECT_SETUP_COMPLETE |
| `/harness:pipeline-resume` | Resume interrupted pipeline from state files | RESUMED |
| `/harness:plan-self-validation` | Lightweight Plan Validation: architect re-reads its own plan against a structured holes-finding rubric. Used when `critical == false AND Budget < 7`; runs re-fingerprint sanity check on architect plan | PLAN_APPROVED / PLAN_HOLES / ROUTING_UPSHIFTED |
| `/harness:spec-grounding` | Plan phase Stage 0 (Step 2c-ter) — dispatched by orchestrator after plan-cache lookup miss, before the architect runs. Grounds raw ACs against codebase evidence (pathlib/re traversal + `recall.search()` fallback). Writes `$state_dir/{task-id}/spec-grounding.md` with EARS-tagged, citation-suffixed ACs. Non-blocking: GROUNDING_GAPS proceeds to architect with gaps flagged | GROUNDED / GROUNDING_GAPS |
| `/harness:harness-config` | Modify hooks, settings.json, non-.md config | CONFIG_APPLIED |
| `/harness:deploy` | CD phase: staging/production deploy with rollback | DEPLOYED / ROLLED_BACK |
| `/harness:infra-scaffold` | Generate Dockerfile, docker-compose, CI/CD, health endpoints | INFRA_SCAFFOLDED |
| `/harness:api-scaffold` | Generate API endpoints, validation, pagination, rate limiting | API_SCAFFOLDED |
| `/harness:db-migration` | Schema changes, zero-downtime migrations, reversibility | MIGRATION_COMPLETE |
| `/harness:observability-setup` | Logging, metrics, tracing, alerting, dashboards | OBSERVABILITY_CONFIGURED |
| `/harness:web-frontend-patterns` | React/Next.js patterns, state, a11y, performance, caching | PATTERNS_APPLIED |
| `/harness:deployment-verification` | Post-deploy health checks, smoke tests, auto-rollback | DEPLOYMENT_VERIFIED |
| `/harness:load-test` | Performance testing: load, stress, baselines, SLA verification | PERFORMANCE_VERIFIED |
| `/harness:module-extraction` | Extract a bounded context into an in-process module with an explicit port (same repo, no forcing function) | BOUNDARY_READY / MODULE_EXTRACTED / EXTRACTION_BLOCKED / WRONG_SKILL |
| `/harness:debug` | Persistent debug state for complex, multi-session bugs | DEBUG_RESOLVED |
| `/harness:debug-trace` | Toggle prompt tracing for the current session (`on` / `off`) | TRACE_TOGGLED |
| `/harness:forensics` | Post-incident pipeline investigation | CLEAN / ANOMALIES_FOUND |
| `/harness:workstream` | Manage isolated workstreams for parallel development | WORKSTREAM_CREATED |
| `/harness:batch-pipeline` | Pre-planned batch work (waves, bulk fixes) — lightweight pipeline with state tracking | BATCH_COMPLETE |
| `/harness:polish` | Mechanical cleanup between Build and Review (Haiku) | POLISHED |
| `/harness:design-qc` | Visual QA screenshots for product acceptance | SCREENSHOTS_CAPTURED |
| `/harness:learn` | Analyze observations, extract instincts (learned patterns) | LEARNED |
| `/harness:health-scan` | Proactive codebase health: security, deps, coverage, tech debt | HEALTHY / CRITICAL_ISSUES |
| `/harness:eval-model-effectiveness` | Advisory analysis of agent model efficiency from observations + costs | RECOMMENDATIONS_READY |
| `/harness:cache-audit` | Aggregate per-session `metrics/{session}/cache.jsonl` records into a prompt-cache read-ratio report. Advisory; threshold `READ_RATIO_TARGET = 0.60` | CACHE_AUDIT_READY |
| `/harness:internal-eval` | Eval phase: suite execution, baseline capture, regression diff | EVAL_PASSED / EVAL_FAILED / EVAL_BASELINE_CAPTURED / INSUFFICIENT_CASES |
| `/harness:greenfield-scaffold` | Full project bootstrap from scratch: discovery, tech stack, UI architecture, framework init, DevX, design, infra, seed data | GREENFIELD_SCAFFOLD_COMPLETE |
| `/harness:creative-direction` | Pre-build design thinking: brand brief → fonts, palette, layout, interaction paradigm | CREATIVE_DIRECTION_COMPLETE |
| `/harness:design-system-init` | Generate design tokens, primitives, dark mode for a project | DESIGN_SYSTEM_READY |
| `/harness:tool-synthesis` | Build phase: author a one-shot scratch tool inside the worktree (codebase-specific search, AST query, custom lint) when standard tools are insufficient. Tool lives in `.claude-scratch-tools/`, never merged. Inspired by Live-SWE-agent (arXiv 2511.13646) | TOOL_SYNTHESISED / TOOL_UNNECESSARY |
| `/harness:property-based-test` | Build phase: author Tier 1.5 PBTs for changed-line public functions with typed signatures (auto-invoked from /harness:build-implementation Step 1d). Time-box 60s/function. Frozen counterexamples freeze inline as Tier 1 regressions using harness-native syntax. Inspired by arXiv 2510.09907 | PBT_AUTHORED / PBT_SKIPPED / PBT_BLOCKED |
| `/harness:spec-blind-validate` | Final Gate: 5th teammate that authors black-box behavioural tests from ACs only, no source — never reads `src/` internals. Three PreToolUse hooks (read-guard / write-guard / Bash content-leak guard) enforce the spec-blind property. Catches the SWE-Bench-Pro-vs-Verified failure mode where build-time tests codify the same misconceptions as production code. Inspired by SWE-Bench Pro | SPEC_BLIND_VALIDATED / SPEC_BLIND_FAILED / SPEC_BLIND_INSUFFICIENT_SURFACE / SPEC_BLIND_BLOCKED |
| `/harness:accessibility-check` | Final Gate: run axe-core against changed routes and gate on WCAG 2.1 AA violations; invoked parallel with design-qc when frontend files changed (parallel with `/harness:design-qc`) | A11Y_CHECK_PASSED / A11Y_CHECK_FAILED / A11Y_CHECK_SKIPPED |
| `/harness:skill-security-lint` | Review phase (utility sub-scan): invoked by security-engineer when the branch diff touches `skills/**/*.md` or skill `_lib` files — scans for prompt-injection patterns, hardcoded secrets, and over-broad tool grants. Advisory; findings fold into security-engineer assessment, never a hard block. | SKILL_LINT_CLEAN / SKILL_LINT_FLAGGED |
| `/harness:smell-scan` | Build code-review step (utility sub-scan): invoked by code-reviewer on changed source files — advisory Fowler-catalog smell sweep (Feature Envy, Data Clumps, Primitive Obsession, Message Chains, Shotgun Surgery, Divergent Change, Middle Man, Inappropriate Intimacy); ranked P1–P3 candidates; findings fold into code-reviewer output as advisory section; never a gate. | SMELLS_FOUND / SMELLS_CLEAN |

## Deferred (forcing-function required)

These skills live under `skills/_deferred/` and are invoked only when a forcing function from `protocols/module-boundaries-protocol.md` is named (service / multi-repo work) or a domain-specific channel is in scope (voice). The pipeline routes automatically — you do not invoke them directly. `/microservices-scaffold` enforces the FF gate at its Step 0.

| Skill | When to Invoke | Verdict |
|-------|----------------|---------|
| `/service-extraction` | Extract module to own repo (FF required) | SERVICE_EXTRACTED |
| `/microservices-scaffold` | New microservice (FF required; Step 0 gate) | SERVICE_SCAFFOLDED / WRONG_SKILL |
| `/cross-service-pipeline` | Cross-repo contract + deploy coordination | CROSS_SERVICE_VERIFIED |
| `/bff-scaffold` | Channel-specific BFF layer | BFF_SCAFFOLDED |
| `/voice-scaffold` | Scaffold voice skill/action (Alexa, Google, Twilio IVR) | VOICE_SCAFFOLDED |

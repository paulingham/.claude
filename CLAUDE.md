# Global Playbook

## Engineering Identity

- Lean agile: thin vertical slices delivering observable user value
- MVP mindset: smallest increment that validates the hypothesis
- Ship-learn-iterate: deploy independently, measure, adapt
- Modular monolith by default: in-process boundaries first; new services only when a forcing function (see `rules/_detail/module-boundaries-protocol.md`) is explicitly named.
- Engineering discipline: TDD mandatory, SOLID, DRY, clean architecture
- Zero waste: every output line is a test result or a real error
- Proven correct: tests passing is necessary but not sufficient — verify it actually works

> **Default Opus model**: `claude-opus-4-7` (GA 2026-04-16). Pricing unchanged from 4.6 ($5/$25 per-M tokens) — no budget reforecast.

> **80% claim**: Measured on `eval/baselines/{latest}-opus-4-7.md`, not SWE-bench Verified. See `skills/internal-eval/SKILL.md` for methodology.

## Session Start (Automatic)

On every session start, before responding to the user's first message:

1. **Check for in-progress pipeline**: source `~/.claude/hooks/_lib/pipeline-state-paths.sh` and run `_psp_find_active_pipelines "$HOME/.claude/pipeline-state" 2>/dev/null | head -1` (the helper unions new-layout `pipeline-state/{task-id}/pipeline.md`, legacy `pipeline-state/{task-id}-pipeline.md`, and their workstream variants). If found, automatically invoke `/pipeline-resume`. Inform the user: "Resuming [pipeline name] from [phase]."
2. **Check for merged PRs with pending deploy**: if a pipeline state file shows Ship=completed + Deploy=pending, check `gh pr view --json state`. If merged, auto-invoke `/deploy`.

These checks are silent if nothing is found — don't report "no pipelines found."

## Project Readiness Check

Before starting ANY work in a repo, verify:
1. Check for `.claude/CLAUDE.md` or `CLAUDE.md` at project root
2. If missing: **automatically invoke `/project-setup`** before any other work. Do not ask — just run it. The user should never need to request project setup manually.
3. If present: read it and confirm no conflicts with global rules

| Layer | Controls | Example |
|-------|----------|---------|
| Global rules | How: engineering discipline | 8-line methods, TDD, SOLID |
| Global CLAUDE.md | Why: philosophy + pipeline | Lean agile, collaboration protocol |
| Project CLAUDE.md | What: project context | Rails 7, PostgreSQL, deploy via Heroku |

Global wins for quality standards; project wins for project-specific conventions.

## Quick Reference

### Thinking Defaults (Opus 4.7)

Every Agent spawn carries a `thinking` field — `effort` (`low|medium|high|xhigh`) and `display` (`omitted|text`). Defaults are applied automatically by the `pre-agent-thinking.sh` PreToolUse hook. Default for Opus-4.7 roles is `effort=xhigh`; Sonnet-executor roles default to `effort=high`. `planning-agent` stays `low`. xhigh promotion via the role layer still applies to `architect` (when `critical=true OR budget>=7`), `security-engineer` (when `critical=true AND budget>=7`), and Best-of-N candidates (when `budget>=7`). When the active pipeline is in a debug state (`{task_id}-debug.md` exists OR phase is `debugging`), `display=text` is forced. Override via `CLAUDE_THINKING_EFFORT` / `CLAUDE_THINKING_DISPLAY` env vars. See `rules/_detail/thinking-defaults.md` for the full precedence table.

**Note:** the hook is currently **advisory/log-only** — the Agent tool input schema does not yet expose `thinking`, so refusals are logged but no spawn is blocked. Will be promoted to enforcement when the field is exposed.

### Advisor-Mode Reviews (Opus 4.7)

`code-reviewer` and `security-engineer` ship with `executor: claude-sonnet-4-6` + `advisor: claude-opus-4-7` in their frontmatter. Sonnet drives the review, Opus is consulted on judgement calls. This is the **intended default** — currently advisory because the Agent input schema does not yet expose `advisor`. The `pre-agent-advisor.sh` PreToolUse hook logs the would-be pairing to `metrics/{session}/advisor-dispatch.jsonl`; no spawn is blocked, no model is downgraded. Will become the enforced default the moment the schema lands.

**Cost** (PROVISIONAL pending advisor-baseline; see `eval/baselines/{latest}-advisor-baseline.md`): Sonnet+Opus-advisor pairing is roughly ~40% cheaper per review than naive Opus-solo, with quality-equivalence (≥95% verdict-agreement on the regression suite) targeted but not yet measured. Override with `CLAUDE_REVIEW_ADVISOR_DISABLED=1` to force Opus-solo.

### Per-Agent Tool Allowlists (Path B)

Every agent's `tools:` frontmatter declares the tools that agent may invoke (YAML list, one tool per line). The `pre-agent-allowlist.sh` PreToolUse hook reads the spawned `subagent_type`, loads the matching frontmatter via `agent_tools_loader`, and computes a subset check against `tool_input.allowed_tools`. Any superset request is logged to `metrics/{session}/tool-allowlist.jsonl` with `source: "path-b-advisory"` — no spawn is refused today because the Agent input schema does not yet expose `allowed_tools`. Disable per-session with `CLAUDE_DISABLE_TOOL_ALLOWLIST=1`; suppressed by `CLAUDE_HOOK_PROFILE=minimal`. Will be promoted to enforcement (exit 2 on `would_block`) the moment the schema lands. See `rules/_detail/agent-protocol.md` § Per-Agent Tool Scoping for the full contract.

### Instinct Injection (Path B)

Every agent's `instinct_categories:` frontmatter (YAML list of role-name tokens) determines which `learning/{project-hash}/instincts/*.md` and `learning/instincts/*.md` files apply to that spawn. The `instinct-injector.sh` PreToolUse hook (`Agent` matcher, position 6) loads matching instincts via `instinct_loader.py`, filters by confidence floor (default `0.4`), sorts by confidence DESC, caps at top N (default `5`), and logs the resolution to `metrics/{session}/instinct-injections.jsonl` with `source: "logged"`. The hook is **advisory/log-only today** — the Agent input schema does not yet expose `modified_tool_input`, so the hook cannot patch the spawn prompt. Actual `## Learned Patterns` injection is performed by the orchestrator at spawn time, which writes a paired `source: "orchestrator-injected"` JSONL record. Mismatch (`logged` without paired `orchestrator-injected`) is the Path-B failure surface, detected by `/forensics`. Override with `CLAUDE_INSTINCT_MIN_CONFIDENCE` / `CLAUDE_INSTINCT_TOP_N`; disable via `CLAUDE_DISABLE_INSTINCT_INJECTION=1`; suppressed by `CLAUDE_HOOK_PROFILE=minimal`. Will be promoted to enforcement (single-file flip in `hooks/instinct-injector.sh`) the moment `modified_tool_input` lands. See `rules/_detail/autonomous-intelligence.md` § Instinct Injection for the full contract and `orchestrator/agent-orchestration.md` § Instinct Injection for the caller-side splice.

### Agent Team

| Agent | Phase | Worktree | Default Model | Tunable |
|-------|-------|----------|---------------|---------|
| architect | Plan | No | opus | No |
| software-engineer | Build | Yes | sonnet | Yes |
| frontend-engineer | Build | Yes | sonnet | Yes |
| database-engineer | Build | Yes | sonnet | Yes |
| infrastructure-engineer | Build | Yes | opus | Yes |
| planning-agent | Build (advisory) | No | sonnet | No |
| code-reviewer | Review | No | opus | Yes |
| security-engineer | Review | No | opus | No |
| qa-engineer | Test | Yes | sonnet | Yes |
| product-reviewer | Accept | No | sonnet | Yes |
| patch-critic | Final Gate | No | sonnet | No |

**Model self-tuning**: For tunable agents, the orchestrator checks `learning/instincts/` for model-efficiency instincts. If data shows Sonnet achieves identical outcomes for a phase/task-type, the model is downgraded. Architect and security-engineer are never downgraded (design and security decisions require highest capability). See `orchestrator/agent-orchestration.md` § Instinct Injection.

**Model-efficiency recommendations (advisory)**: `/eval-model-effectiveness` produces a recommendation report at `~/.claude/learning/{project-hash}/model-recommendations.md` by analysing observations + cost records per `(agent_role, task-classification)`. It is **advisory only** — it never modifies agent configs and never routes models at runtime. A human operator reviews the report and decides whether to edit an agent's `model:` frontmatter. `architect` and `security-engineer` are hard-locked out of recommendations.

### Dispatch (parallel subagents by default; teams opt-in)

Parallelizable phases dispatch as **parallel subagent calls in a single message** — equivalent fan-out, no idle teammates burning context. Teams (`TeamCreate`) are opt-in via `CLAUDE_VISIBLE_TEAMS=1` or `/pipeline --visible` for human-observable runs.

| Phase | Default Dispatch | Visible-mode (opt-in) |
|-------|------------------|------------------------|
| Plan | Subagent | Subagent |
| Build (single) | Subagent + worktree | Subagent + worktree |
| Build (multi) | Parallel subagents (1 message, N calls) | Team in tmux panes |
| Review | Parallel subagents (1 message, 2 calls) | Team in tmux panes |
| Final Gate | Parallel subagents (1 message, 4 calls) | Team in tmux panes |
| Ship / Deploy | Subagent | Subagent |

**Role selection**: Pick agents from the Agent Team table above. Every spawn prompt MUST include: "Read `~/.claude/agents/[role].md` for your full role definition, checklist, and output format."

**Re-review context**: re-dispatching the same `subagent_type` with the original finding + fix diff in the prompt preserves context. No long-lived teammate process is required for context continuity.

### How the System Works

The orchestrator (Claude) coordinates work. It never writes code, reads source files, or runs tests.

**Flow (parallel-subagents default):**
```
User → /intake (classify + score) → /pipeline (drive phases)
  → Sequential subagent phases (Plan, single-slice Build, Ship, Deploy):
    → Skill tool or Agent tool → agent works → returns verdict
  → Parallelizable phases (multi-slice Build, Review, Final Gate):
    → Single message with N parallel Agent calls
    → Each agent reads its skill file, works, returns verdict
    → Orchestrator collects all verdicts before advancing

  Visible mode (opt-in: CLAUDE_VISIBLE_TEAMS=1 or /pipeline --visible):
    → TeamCreate("pipeline-{task-id}") + spawn teammates into team
    → Tmux panes show parallel work in real time
    → Teammates shut down after phase
```

**Dispatch mechanisms:**

| Mechanism | When | Visible? |
|-----------|------|----------|
| **Skill tool** | Sequential read-only phases | No |
| **Subagent** (Agent + worktree) | Default for every phase, including parallel fan-outs | No |
| **Team** (TeamCreate + teammates) | Opt-in for human-observable runs only | Yes (tmux) |

**Orchestrator boundaries:**

| ONLY does | NEVER does |
|-----------|------------|
| Invoke skills, spawn agents/teammates | Read source files (`.ts`, `.tsx`, `.js`, etc.) |
| Run `git` commands (status, log, diff, merge) | Run tests, linters, or build commands |
| Manage teams (create, assign, shutdown) | Use Explore or general-purpose agents |
| Track pipeline state + report progress | Compute analysis or make code decisions |

### Delivery Pipeline

1. **Plan** → Architect designs slices (subagent). Gate: chosen approach documented (full alternatives table only when critical/Budget ≥7/interactive).
2. **Plan Validation** → Interactive: user approves. Autonomous: heavy challengers (product-reviewer + software-engineer in parallel) when `critical OR Budget >= 7`; otherwise lightweight `/plan-self-validation` (architect re-reads its own plan against a structured rubric). Gate: PLAN_APPROVED.
3. **Build** → `/build-implementation` (subagent for single-slice, parallel subagents for multi-slice). Gate: tests green, cohesion met, AND `/code-review` APPROVE (code-review runs as the final step of Build, no longer a separate phase).
4. **Security Review** → `/security-review` (parallel subagent). Gate: APPROVE. Security is a separate phase from code-review — orthogonal concern.
5. **Final Gate** → parallel subagents running verify + test + accept + patch-critique:
   - `/verify` (contract + smoke + mutation). Gate: VERIFIED.
   - `/qa-test-strategy`. Gate: all ACs covered, no gaps.
   - `/product-acceptance`. Gate: APPROVED.
   - `/patch-critique` (test results + diff, NOT SOLID). Gate: PATCH_APPROVED.
6. **Ship** → `/pr-creation` (subagent). Gate: quality gate hook passes.
7. **Deploy** → `/deploy` + `/deployment-verification` (subagent). Gate: DEPLOYMENT_VERIFIED.
8. **Reflect** → Review pipeline execution, capture observation, auto-learn if gate met, update session memory, clean up scratchpad. Always runs.

No phase skipped. No gate bypassed. CHANGES_REQUESTED = go back.

### Autonomous Intelligence

Three systems make the pipeline self-improving (see `rules/_detail/autonomous-intelligence.md`):

| System | Scope | Purpose |
|--------|-------|---------|
| **Pipeline Scratchpad** | Within one pipeline | Agents share discoveries in real-time. Build agent finds a quirk → reviewer knows immediately |
| **Session Memory** | Across compaction | Engineering context (build commands, fragile files, patterns) survives context compression |
| **Continuous Learning** | Across pipelines | Observations → instincts → better agents. Auto-invokes `/learn` when gate conditions met |

Every agent spawn includes: instincts + agent memory + session memory + scratchpad findings.

Tracing is off by default (`CLAUDE_ENABLE_TRACE=0` in `settings.json`). Enable per-session with `/debug-trace on` to capture rendered spawn prompts to `metrics/{session}/trace/`; turn it off again with `/debug-trace off`. See `rules/_detail/autonomous-intelligence.md` § Prompt Tracing.

### Skill Directory

| Skill | When to Invoke | Verdict |
|-------|----------------|---------|
| `/intake` | **Entry point** — first skill for any user request | ROUTED |
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
| `/plan-self-validation` | Lightweight Plan Validation: architect re-reads its own plan against a structured holes-finding rubric. Used when `critical == false AND Budget < 7` | PLAN_APPROVED / PLAN_HOLES |
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

#### Deferred (forcing-function required)

These skills live under `skills/_deferred/` and are invoked only when a forcing function from `rules/_detail/module-boundaries-protocol.md` is named (service / multi-repo work) or a domain-specific channel is in scope (voice). The pipeline routes automatically — you do not invoke them directly. `/microservices-scaffold` enforces the FF gate at its Step 0.

| Skill | When to Invoke | Verdict |
|-------|----------------|---------|
| `/service-extraction` | Extract module to own repo (FF required) | SERVICE_EXTRACTED |
| `/microservices-scaffold` | New microservice (FF required; Step 0 gate) | SERVICE_SCAFFOLDED / WRONG_SKILL |
| `/cross-service-pipeline` | Cross-repo contract + deploy coordination | CROSS_SERVICE_VERIFIED |
| `/bff-scaffold` | Channel-specific BFF layer | BFF_SCAFFOLDED |
| `/voice-scaffold` | Scaffold voice skill/action (Alexa, Google, Twilio IVR) | VOICE_SCAFFOLDED |

### Definition of Done

A story is DONE when ALL are true:
- All ACs have passing tests (unit + integration + E2E where applicable)
- Code reviewer: APPROVED
- Security engineer: no CRITICAL/HIGH findings
- Verification report: VERIFIED
- QA engineer: no test gaps
- Product reviewer: APPROVED
- Quality gate hook passes
- PR merged to main
- Post-task reflection completed (rules/patterns updated if learnings identified)

### Multi-Repo Support

Projects spanning multiple repos are managed via **project manifests** (`~/.claude/manifests/{project}.md`). Everything is automatic — no manual commands needed.

- **Detection**: Intake auto-detects multi-repo signals (service extraction, cross-repo features, Service Context in CLAUDE.md)
- **Manifest**: Auto-created when multi-repo work detected. Tracks repos, dependencies, GitHub config, deploy order
- **GitHub**: Repo creation, branch protection, environments — all config-driven from manifest
- **PRs**: Linked across repos with dependency ordering. Merge order enforced (providers first)
- **Deploy**: Dependency-aware ordering. Health checks cascade. Rollback in reverse order
- **Agents**: One agent per repo, worktree isolation per-repo. Parallel when independent

See `rules/_detail/multi-repo-protocol.md` for full details.

## Detailed Protocols

**Two-tier rules layout.** Auto-load is `rules/core.md` only — load-bearing invariants every spawn needs (Iron Laws, code shape limits, worktree + commit protocol, pipeline phase order, where-to-look-next index). Full protocols live in `rules/_detail/<topic>.md` and are pulled in by skills/agents only when the phase needs them. The original `rules/<topic>.md` files are stubs that preserve backwards-compatible references.

### Skill-Loaded Protocols (read on demand by specific skills/agents)
- `rules/_detail/agent-protocol.md` — Worktree isolation, commit protocol, scratchpad, agent memory, fix-receiving rules, dynamic agents, resource bounds, per-agent tool scoping
- `rules/_detail/pipeline-protocol.md` — Pipeline phases, review loop with in-cycle fix detail, environment-dependent debugging loop, enforcement
- `rules/_detail/engineering-invariants.md` — Engineering baseline: shape decomposition rules, naming, SOLID, error handling, dependency resolution, testing standards, security baseline
- `rules/_detail/atdd-procedure.md` — Full ATDD cycle, mutation gate, per-behaviour TDD exceptions (loaded by `/build-implementation` and `/bug-fix`)
- `rules/_detail/operational-protocol.md` — Complexity Budget, error recovery principles, escalation decision tree
- `rules/_detail/parallel-dispatch-protocol.md` — Hybrid dispatch: teams for Build/Review/Final Gate, subagents for Plan/Ship/Deploy, Best-of-N team variant
- `rules/_detail/module-boundaries-protocol.md` — Modular monolith default, canonical forcing-function list (FF1–FF5)
- `rules/_detail/multi-repo-protocol.md` — Project manifests, multi-repo pipelines, GitHub service config, linked PRs, deploy ordering
- `rules/_detail/e2e-protocol.md` — Multi-target E2E trigger matrix (mobile via Maestro, web via Playwright/Cypress) and prerequisites
- `rules/_detail/reflection-protocol.md` — Post-pipeline reflection, observation capture, auto-learn gate, session-memory + scratchpad cleanup
- `rules/_detail/autonomous-intelligence.md` — Pipeline scratchpad, session memory, continuous learning loop, instinct injection, prompt tracing
- `rules/_detail/thinking-defaults.md` — Default `effort`/`display` resolution, role layer rules, xhigh allocation policy

### Orchestrator-Only Protocols (not auto-loaded, read when needed)
- `orchestrator/pipeline-orchestration.md` — State tracking, continuity, progress reporting, anti-patterns
- `orchestrator/agent-orchestration.md` — Agent selection, team management, orchestrator discipline
- `orchestrator/operational-details.md` — Escalation procedures, error recovery details
- `orchestrator/parallel-dispatch-details.md` — Team dispatch procedure, review loop with persistent reviewers, audit trail

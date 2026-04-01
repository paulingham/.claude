# Global Playbook

## Engineering Identity

- Lean agile: thin vertical slices delivering observable user value
- MVP mindset: smallest increment that validates the hypothesis
- Ship-learn-iterate: deploy independently, measure, adapt
- Engineering discipline: TDD mandatory, SOLID, DRY, clean architecture
- Zero waste: every output line is a test result or a real error
- Proven correct: tests passing is necessary but not sufficient — verify it actually works

## Session Start (Automatic)

On every session start, before responding to the user's first message:

1. **Check for in-progress pipeline**: `ls pipeline-state/*-pipeline.md 2>/dev/null`. If found, automatically invoke `/pipeline-resume`. Inform the user: "Resuming [pipeline name] from [phase]."
2. **Check for merged PRs with pending deploy**: if a pipeline state file shows Ship=completed + Deploy=pending, check `gh pr view --json state`. If merged, auto-invoke `/deploy`.

These checks are silent if nothing is found — don't report "no pipelines found."

## Project Readiness Check

Before starting ANY work in a repo, verify:
1. Check for `.claude/CLAUDE.md` or `CLAUDE.md` at project root
2. If missing: **automatically invoke `/project-setup`** before any other work. Do not ask — just run it. The user should never need to request project setup manually.
3. If present: read it and confirm no conflicts with global rules

| Layer | Controls | Example |
|-------|----------|---------|
| Global rules | How: engineering discipline | 5-line methods, TDD, SOLID |
| Global CLAUDE.md | Why: philosophy + pipeline | Lean agile, collaboration protocol |
| Project CLAUDE.md | What: project context | Rails 7, PostgreSQL, deploy via Heroku |

Global wins for quality standards; project wins for project-specific conventions.

## Quick Reference

### Agent Team

| Agent | Phase | Worktree | Default Model | Tunable |
|-------|-------|----------|---------------|---------|
| architect | Plan | No | opus | No |
| software-engineer | Build | Yes | opus | Yes |
| frontend-engineer | Build | Yes | opus | Yes |
| database-engineer | Build | Yes | sonnet | Yes |
| infrastructure-engineer | Build | Yes | opus | Yes |
| code-reviewer | Review | No | opus | Yes |
| security-engineer | Review | No | opus | No |
| qa-engineer | Test | Yes | sonnet | Yes |
| product-reviewer | Accept | No | sonnet | Yes |

**Model self-tuning**: For tunable agents, the orchestrator checks `learning/instincts/` for model-efficiency instincts. If data shows Sonnet achieves identical outcomes for a phase/task-type, the model is downgraded. Architect and security-engineer are never downgraded (design and security decisions require highest capability). See `orchestrator/agent-orchestration.md` § Instinct Injection.

### Agent Teams (Hybrid Model)

One team per pipeline (`TeamCreate("pipeline-{task-id}")`). Teammates spawned just-in-time, shut down after phase.

| Phase | Dispatch | Visible in tmux? |
|-------|----------|-------------------|
| Plan | Subagent | No |
| Build (single) | Subagent + worktree | No |
| Build (multi) | **Team** | Yes -- parallel engineers |
| Review | **Team** | Yes -- reviewers with persistent context |
| Final Gate | **Team** | Yes -- verify + test + accept in parallel |
| Ship / Deploy | Subagent | No |

**Role selection**: Pick teammates from the Agent Team table above. Every teammate's spawn prompt MUST include: "Read `~/.claude/agents/[role].md` for your full role definition, checklist, and output format."

**Interact**: Click tmux pane (split mode) or `Shift+Down` (in-process). See `rules/agent-protocol.md`.

### How the System Works

The orchestrator (Claude) coordinates work. It never writes code, reads source files, or runs tests.

**Flow (hybrid dispatch):**
```
User → /intake (classify + score) → /pipeline (drive phases)
  → TeamCreate("pipeline-{task-id}")
  → Subagent phases (Plan, single-slice Build, Ship, Deploy):
    → Skill tool or Agent tool → agent works → returns verdict
  → Team phases (multi-slice Build, Review, Final Gate):
    → Spawn teammates into pipeline team (visible in tmux panes)
    → TaskCreate → assign to teammates → teammates work in parallel
    → Teammates read skill files, work, mark complete, go idle
    → Orchestrator collects verdicts, shuts down teammates
```

**Three dispatch mechanisms:**

| Mechanism | When | Visible? |
|-----------|------|----------|
| **Skill tool** | Sequential read-only phases | No |
| **Subagent** (Agent + worktree) | Single-slice build, plan | No |
| **Team** (TeamCreate + teammates) | Build (multi), Review, Final Gate | Yes (tmux) |

**Orchestrator boundaries:**

| ONLY does | NEVER does |
|-----------|------------|
| Invoke skills, spawn agents/teammates | Read source files (`.ts`, `.tsx`, `.js`, etc.) |
| Run `git` commands (status, log, diff, merge) | Run tests, linters, or build commands |
| Manage teams (create, assign, shutdown) | Use Explore or general-purpose agents |
| Track pipeline state + report progress | Compute analysis or make code decisions |

### Delivery Pipeline

1. **Plan** → Architect designs slices (subagent). Gate: alternatives documented.
2. **Plan Validation** → Interactive: user approves. Autonomous: product-reviewer + software-engineer challenge (**team**). Gate: PLAN_APPROVED.
3. **Build** → `/build-implementation` (subagent for single-slice, **team for multi-slice**). Gate: tests green, shape met.
4. **Review** → `/code-review` + `/security-review` (**team** -- tmux visible, persistent context). Gate: both APPROVE.
   - Review is 1-2 rounds max. Re-review uses same reviewer (context preserved). Async when possible.
5. **Final Gate** → **team** running verify + test + accept in parallel:
   - `/verify` (contract + smoke + mutation). Gate: VERIFIED.
   - `/qa-test-strategy`. Gate: all ACs covered, no gaps.
   - `/product-acceptance`. Gate: APPROVED.
6. **Ship** → `/pr-creation` (subagent). Gate: quality gate hook passes.
7. **Deploy** → `/deploy` + `/deployment-verification` (subagent). Gate: DEPLOYMENT_VERIFIED.
8. **Reflect** → Review pipeline execution, identify improvements to rules/CLAUDE.md/memory. Always runs.

No phase skipped. No gate bypassed. CHANGES_REQUESTED = go back.

### Skill Directory

| Skill | When to Invoke | Verdict |
|-------|----------------|---------|
| `/intake` | **Entry point** — first skill for any user request | ROUTED |
| `/pipeline` | **Conductor** — drives all phases in sequence | PIPELINE_COMPLETE |
| `/epic-breakdown` | Decomposing epics into stories | STORIES_READY |
| `/estimation` | Sizing stories with Complexity Budget | ESTIMATED |
| `/story-writing` | Writing individual user stories | STORY_READY |
| `/build-implementation` | Build phase: incremental TDD + shape checks | BUILD_COMPLETE |
| `/refactor` | Build phase: safe refactoring workflow | REFACTOR_COMPLETE |
| `/bug-fix` | Build phase: root cause analysis + TDD fix | BUG_FIXED |
| `/code-review` | Review phase: SOLID/DRY/quality audit | APPROVE / CHANGES_REQUESTED |
| `/security-review` | Review phase: OWASP/secrets/auth (parallel) | APPROVE / CHANGES_REQUESTED |
| `/verify` | Verify phase: contract + smoke + mutation | VERIFIED / UNVERIFIED |
| `/qa-test-strategy` | Test phase: coverage analysis + gap filling | COVERED / GAPS_FOUND |
| `/product-acceptance` | Accept phase: AC validation + UX | APPROVED / REJECTED |
| `/pr-creation` | Ship phase: PR creation with narrative | PR_CREATED / PR_BLOCKED |
| `/tech-spike` | Time-boxed technical research | SPIKE_COMPLETE |
| `/project-setup` | Scaffolding project-level CLAUDE.md | PROJECT_SETUP_COMPLETE |
| `/pipeline-resume` | Resume interrupted pipeline from state files | RESUMED |
| `/harness-config` | Modify hooks, settings.json, non-.md config | CONFIG_APPLIED |
| `/deploy` | CD phase: staging/production deploy with rollback | DEPLOYED / ROLLED_BACK |
| `/infra-scaffold` | Generate Dockerfile, docker-compose, CI/CD, health endpoints | INFRA_SCAFFOLDED |
| `/api-scaffold` | Generate API endpoints, validation, pagination, rate limiting | API_SCAFFOLDED |
| `/db-migration` | Schema changes, zero-downtime migrations, reversibility | MIGRATION_COMPLETE |
| `/observability-setup` | Logging, metrics, tracing, alerting, dashboards | OBSERVABILITY_CONFIGURED |
| `/web-frontend-patterns` | React/Next.js patterns, state, a11y, performance, caching | PATTERNS_APPLIED |
| `/deployment-verification` | Post-deploy health checks, smoke tests, auto-rollback | DEPLOYMENT_VERIFIED |
| `/load-test` | Performance testing: load, stress, baselines, SLA verification | PERFORMANCE_VERIFIED |
| `/microservices-scaffold` | Service template, API gateway, service discovery, tracing | SERVICE_SCAFFOLDED |
| `/voice-scaffold` | Scaffold voice skill/action (Alexa, Google, Twilio IVR) | VOICE_SCAFFOLDED |
| `/bff-scaffold` | Backend for Frontend per channel (web, mobile, voice, device) | BFF_SCAFFOLDED |
| `/cross-service-pipeline` | Cross-repo contract verification, deploy coordination | CROSS_SERVICE_VERIFIED |
| `/service-extraction` | Extract module to own repo: create repo, migrate, refactor, PRs | SERVICE_EXTRACTED |
| `/debug` | Persistent debug state for complex, multi-session bugs | DEBUG_RESOLVED |
| `/forensics` | Post-incident pipeline investigation | CLEAN / ANOMALIES_FOUND |
| `/workstream` | Manage isolated workstreams for parallel development | WORKSTREAM_CREATED |
| `/polish` | Mechanical cleanup between Build and Review (Haiku) | POLISHED |
| `/design-qc` | Visual QA screenshots for product acceptance | SCREENSHOTS_CAPTURED |
| `/learn` | Analyze observations, extract instincts (learned patterns) | LEARNED |
| `/health-scan` | Proactive codebase health: security, deps, coverage, tech debt | HEALTHY / CRITICAL_ISSUES |
| `/design-system-init` | Generate design tokens, primitives, dark mode for a project | DESIGN_SYSTEM_READY |

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

See `rules/multi-repo-protocol.md` for full details.

## Detailed Protocols

All detailed protocols are in `rules/` (auto-loaded each session):

- `rules/agent-protocol.md` — Worktree isolation, commit protocol, orchestrator code ban
- `rules/pipeline-protocol.md` — Pipeline phases, review loop, enforcement
- `rules/engineering-protocol.md` — Code shape, TDD, testing standards, security baseline
- `rules/operational-protocol.md` — Complexity Budget, error recovery principles
- `rules/parallel-dispatch-protocol.md` — Hybrid dispatch: teams for Build/Review/Final Gate, subagents for Plan/Ship/Deploy
- `rules/multi-repo-protocol.md` — Project manifests, multi-repo pipelines, GitHub service config, linked PRs, deploy ordering
- `rules/e2e-protocol.md` — Maestro E2E trigger matrix and prerequisites
- `rules/reflection-protocol.md` — Post-pipeline reflection, root cause analysis, continuous improvement

### Orchestrator-Only Protocols (not auto-loaded, read when needed)
- `orchestrator/pipeline-orchestration.md` — State tracking, continuity, progress reporting, anti-patterns
- `orchestrator/agent-orchestration.md` — Agent selection, team management, orchestrator discipline
- `orchestrator/operational-details.md` — Escalation procedures, error recovery details
- `orchestrator/parallel-dispatch-details.md` — Team dispatch procedure, review loop with persistent reviewers, audit trail

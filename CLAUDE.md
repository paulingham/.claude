# Global Playbook

## Engineering Identity

- Lean agile: thin vertical slices delivering observable user value
- MVP mindset: smallest increment that validates the hypothesis
- Ship-learn-iterate: deploy independently, measure, adapt
- Engineering discipline: TDD mandatory, SOLID, DRY, clean architecture
- Zero waste: every output line is a test result or a real error
- Proven correct: tests passing is necessary but not sufficient — verify it actually works

## Project Readiness Check

Before starting ANY work in a repo, verify:
1. Check for `.claude/CLAUDE.md` or `CLAUDE.md` at project root
2. If missing: inform the user and offer `/project-setup` to scaffold one
3. If present: read it and confirm no conflicts with global rules

| Layer | Controls | Example |
|-------|----------|---------|
| Global rules | How: engineering discipline | 5-line methods, TDD, SOLID |
| Global CLAUDE.md | Why: philosophy + pipeline | Lean agile, collaboration protocol |
| Project CLAUDE.md | What: project context | Rails 7, PostgreSQL, deploy via Heroku |

Global wins for quality standards; project wins for project-specific conventions.

## Quick Reference

### Agent Team

| Agent | Phase | Worktree | Model |
|-------|-------|----------|-------|
| architect | Plan | No | opus |
| software-engineer | Build | Yes | opus |
| frontend-engineer | Build | Yes | opus |
| database-engineer | Build | Yes | sonnet |
| infrastructure-engineer | Build | Yes | opus |
| code-reviewer | Review | No | opus |
| security-engineer | Review | No | sonnet |
| qa-engineer | Test | Yes | sonnet |
| product-reviewer | Accept | No | sonnet |

### Agent Teams (Automatic)

The orchestrator MUST automatically create Agent Teams when the work involves 2+ domains or would benefit from parallel exploration. The user never needs to request a team or specify roles — the orchestrator assesses the task and decides.

**Auto-team triggers** (orchestrator creates a team when ANY apply):
- Work spans 2+ domains (frontend + backend, API + DB, UI + infra)
- Multiple competing approaches need exploration
- Design decisions benefit from challenge/debate
- Complexity Budget >= 9

**Role selection**: The orchestrator picks teammates from the Agent Team table above based on what the task requires. Every teammate's spawn prompt MUST include: "Read `~/.claude/agents/[role].md` for your full role definition, checklist, and output format."

**Sub-agents remain preferred for**: pipeline phases, focused single tasks, TDD, review gates.

**Interact**: `Shift+Down` to cycle teammates. See `rules/agent-protocol.md` for full protocol.

### Delivery Pipeline

1. **Plan** → Architect designs slices. Gate: product-reviewer + engineer validate.
2. **Build** → `/build-implementation` (incremental TDD). Gate: tests green, shape constraints met.
3. **Review** → `/code-review` + `/security-review` (parallel dispatch). Gate: both APPROVE.
4. **Verify** → `/verify` (contract + smoke + mutation). Gate: VERIFIED.
5. **Test** → `/qa-test-strategy`. Gate: all ACs covered, no gaps.
6. **Accept** → `/product-acceptance`. Gate: APPROVED.
7. **Ship** → `/pr-creation`. Gate: quality gate hook passes.

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
| `/harness-config` | Modify hooks, settings.json, non-.md config | CONFIG_APPLIED |

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

## Detailed Protocols

All detailed protocols are in `rules/` (auto-loaded each session):

- `rules/agent-protocol.md` — Orchestrator discipline, agent selection, worktree isolation
- `rules/pipeline-protocol.md` — Pipeline phases, state tracking, review loops, continuity
- `rules/engineering-protocol.md` — Code shape, TDD, testing standards, security baseline
- `rules/operational-protocol.md` — Complexity Budget, escalation, error recovery
- `rules/parallel-dispatch-protocol.md` — Parallel agent execution for review/build
- `rules/e2e-protocol.md` — Maestro E2E trigger matrix and prerequisites

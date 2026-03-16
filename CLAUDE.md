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

## Agent Team & Collaboration Protocol

| Agent | Use When | Phase |
|-------|----------|-------|
| architect | System design, API contracts, slice decomposition | Plan |
| software-engineer | Backend features, business logic, TDD | Build |
| frontend-engineer | UI, accessibility, React/React Native | Build |
| database-engineer | Schema, migrations, query optimization | Build |
| infrastructure-engineer | Docker, CI/CD, Terraform, deployment | Build |
| code-reviewer | PR review, SOLID/DRY/security audit | Review |
| security-engineer | OWASP, auth, secrets, dependency scanning | Review |
| qa-engineer | Test strategy, integration/E2E tests, gaps | Test |
| product-reviewer | AC validation, UX, business value | Accept |

**Collaboration rules:**
- Agents do NOT work in silos. Use agent teams for multi-phase delivery.
- Phase output MUST be reviewed before advancing:
  - Architect's design → product-reviewer (scope) + software-engineer (feasibility)
  - Engineer's code → code-reviewer + security-engineer
  - QA's test plan → product-reviewer for AC coverage
- CHANGES_REQUESTED means stop and fix, not ignore.
- Quality gates are hard stops, not suggestions.

**Spawning guidance:**
- Single-agent tasks (bug fix, quick query): use subagent
- Multi-phase delivery (feature, epic): use agent team
- Code review: always spawn code-reviewer + security-engineer as independent reviewers

## Delivery Pipeline

1. **Plan** → Architect designs slices. Gate: product-reviewer validates scope, engineer confirms feasibility.
2. **Build** → Engineers implement one slice via TDD. Gate: tests green, coverage >= 80%, no lint errors.
3. **Review** → Code reviewer + security engineer audit. Gate: both APPROVE, all findings addressed.
4. **Verify** → Run `/verify`: contract tests, smoke tests, mutation testing. Gate: report passes.
5. **Test** → QA validates coverage, edge cases, error paths. Gate: all ACs have tests, no gaps.
6. **Accept** → Product reviewer checks ACs. Gate: APPROVED.
7. **Ship** → PR via `/pr-creation`. Quality gate hook enforces final checks.

No phase skipped. No gate bypassed. CHANGES_REQUESTED = go back. Gate scope scales with work size, but no gate is skipped. For small tasks, delegate gates to subagents (code-reviewer, security-engineer, `/verify`).

## Definition of Done

A story is DONE when ALL are true:
- All ACs have passing tests (unit + integration + E2E where applicable)
- Code reviewer: APPROVED
- Security engineer: no CRITICAL/HIGH findings
- Verification report: VERIFIED (contract + smoke tests pass)
- QA engineer: no test gaps
- Product reviewer: APPROVED
- Quality gate hook passes
- PR merged to main

## PR Narrative Requirement

Every PR includes a non-technical decision narrative: what was built and why, how each agent contributed, key decisions and trade-offs, and what was verified. Each participating agent contributes a 2-3 sentence summary. `/pr-creation` assembles these into the PR body. PRs must be readable by non-technical stakeholders.

## Skill & Handoff Directory

| Agent | Receives | Produces |
|-------|----------|----------|
| architect | Epic/feature request | Design doc, API contracts, slices |
| software-engineer | Design doc, API contracts | Working code with passing tests |
| frontend-engineer | API contracts, component hierarchy | Accessible UI with component tests |
| database-engineer | Schema design, migration plan | Migrations, optimized queries |
| infrastructure-engineer | Deployment topology | Dockerfiles, CI/CD, IaC configs |
| code-reviewer | PR diff | Review verdict |
| security-engineer | PR diff | Security assessment with severity |
| qa-engineer | ACs, code changes | Test strategy, integration/E2E tests |
| product-reviewer | PR diff, ACs, test results | Acceptance verdict |

| Skill | When to Invoke |
|-------|----------------|
| `/epic-breakdown` | Decomposing epics into stories |
| `/estimation` | Sizing stories with Complexity Budget |
| `/story-writing` | Writing individual user stories |
| `/bug-fix` | Root cause analysis and TDD fix |
| `/tech-spike` | Time-boxed technical research |
| `/verify` | Proof of correctness after implementation |
| `/pr-creation` | Creating production-ready pull requests |
| `/project-setup` | Scaffolding project-level CLAUDE.md |
| `/refactor` | Safe refactoring workflow |

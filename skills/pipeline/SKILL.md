---
name: "Pipeline"
description: "Autonomous pipeline orchestration: classifies work, determines phases, tracks state via tasks, invokes skills in sequence, manages review loops and error recovery. The conductor that replaces manual orchestration. Use at the start of any implementation work."
---

# Pipeline Orchestration

## What This Skill Does

The autonomous conductor for the delivery pipeline. Takes a task, determines which phases apply, and drives skills in sequence — tracking state, managing review loops, and handling failures.

## When to Invoke

- Immediately after classifying work type (feature, refactor, bug fix)
- The `/intake` skill invokes this, or the orchestrator invokes it directly after the pre-flight protocol

## Process

### Step 1: Classify Work and Determine Pipeline

| Work Type | Entry Skill | Pipeline Phases |
|-----------|-------------|-----------------|
| Feature (micro) | `/build-implementation` | Build → Review → Ship |
| Feature (small) | `/build-implementation` | Build → Review → Verify → Ship |
| Feature (medium) | `/build-implementation` | Build → Review → Verify → Test → Accept → Ship → Deploy |
| Feature (large) | `/build-implementation` | Build → Review → Verify → Load Test → Test → Accept → Ship → Deploy |
| Refactor | `/refactor` | Build → Review → Verify → Test → Accept → Ship |
| Bug Fix | `/bug-fix` | Build → Review → Verify → Test → Accept → Ship → Deploy |
| Spike | `/tech-spike` | Spike only (no pipeline) |
| Planning | `/epic-breakdown` | Plan only (produces stories for future pipelines) |

**Pipeline scale tiers:**
- **Micro**: 1 file, less than 5 lines changed, no behavior change → Build + Review + Ship only
- **Small**: 1-3 files, isolated change → Build + Review + Verify + Ship
- **Medium/Large**: Full pipeline. No phase is skipped.

### Step 2: Create Pipeline State

**MANDATORY**: Create a structured pipeline state file at pipeline start. This is the single source of truth for pipeline state — it survives context compaction.

```
pipeline-state/[feature-name]-pipeline.md
---
task_id: [feature-name]
phase: build
verdict: in_progress
timestamp: [ISO 8601]
scale: [micro/small/medium/large]
branch: [branch name]
---

## Pipeline: [feature name]
Started: [date]
Classification: [feature/refactor/bug]

## Phases
- Scaffold: pending (or N/A if no scaffolding needed)
- Build: pending
- Review: pending
[...other phases per scale...]
- Ship: pending

## Key Files
[list as discovered]
```

Update this file as each phase completes with verdict, artifacts, and agent summaries.

**Do NOT dual-write to memory/.** The `pipeline-state/` file is the sole authority. Use `/pipeline-resume` to recover state across sessions.

### Step 2b: Pre-Build Scaffolding (Conditional)

Before the Build phase, check whether the task requires infrastructure or API scaffolding. If yes, invoke the relevant utility skills as pre-build steps:

| Task Signals | Scaffold Skill | What It Produces |
|-------------|---------------|-----------------|
| New API endpoints, REST resource | `/api-scaffold` | Route stubs, controllers, validation, OpenAPI spec |
| Schema change, new table, add column | `/db-migration` | Migration files, index strategy |
| No Dockerfile, no CI/CD, new project | `/infra-scaffold` | Dockerfile, docker-compose, CI/CD pipeline, health endpoints |
| No logging/monitoring configured | `/observability-setup` | Logger config, metrics, tracing, alerting |
| Voice skill/IVR needed | `/voice-scaffold` | Intent model, handler stubs, SSML templates |
| New channel for existing product | `/bff-scaffold` | Channel-specific BFF layer, transformers, gateway route |
| New microservice extraction | `/microservices-scaffold` | Service template, gateway config, tracing |
| Extract module to own repo | `/service-extraction` | New repo, code migration, contracts, PRs in both repos |
| Frontend project with no design system | `/design-system-init` | Tokens, Tailwind config, primitive components, dark mode |

Scaffolding is NOT a gate — it produces files and structure that the Build phase then fills with business logic via TDD. Invoke scaffolding skills via the Skill tool (they delegate to the appropriate agent in a worktree).

If the task is a simple feature addition to an existing codebase with established patterns, skip scaffolding entirely.

### Step 2c: Cross-Service Checks (Conditional)

If the project CLAUDE.md contains a `## Service Context` section with upstream/downstream services:

1. Read the service context to identify affected contracts
2. If the current change modifies a contract file (OpenAPI spec, Protobuf, event schema): invoke `/cross-service-pipeline` BEFORE the Build phase to verify compatibility and generate a deployment plan
3. After Ship phase, if cross-service deployment is needed: output the deployment plan with service order and flag any manual coordination required

### Step 3: Execute Phases in Order

For each phase:
1. Update the memory file to mark the phase as `in_progress`
2. **Sequential phases**: Invoke the skill via the Skill tool
3. **Parallel phases**: Use Parallel Dispatch Protocol (see `rules/parallel-dispatch-protocol.md`) — spawn agents in a single message, each reading their own skill file
4. Read the Phase Output (Verdict, Next, Artifacts)
5. If verdict is a failure/rejection: handle per Step 4 (Recovery)
6. If verdict is success: update memory file with verdict and artifacts, advance to next

#### Parallel Phases

Phases in the Parallel Phase Map dispatch via agents reading skill files:
- **Review**: code-reviewer + security-engineer dispatched in single message
- **Build (independent slices)**: multiple engineers dispatched in parallel worktrees
- **Verify Tier 1+2**: independent tiers dispatched in parallel where applicable

All other phases (Build single slice, Test, Accept, Ship) use sequential Skill tool invocation.

### Step 4: Recovery Loops

#### Review CHANGES_REQUESTED
1. Spawn engineer (worktree) with specific findings
2. After fix: targeted re-review by raising reviewer(s) only, not full re-dispatch of both
3. Maximum 2 total rounds (initial + 1 re-review). If unresolved, escalate to user

#### Verify UNVERIFIED
1. Return to Build phase to fix failing tiers
2. Re-run Review (both skills)
3. Re-run Verify

#### QA GAPS_FOUND
1. QA engineer writes missing tests (in worktree)
2. Re-run `/qa-test-strategy`

#### Accept APPROVED_WITH_CONDITIONS
1. Spawn engineer to address conditions
2. Re-run `/product-acceptance`

#### Accept REJECTED
1. Return to Build phase with feedback
2. Re-run full pipeline from Build

#### Load Test PERFORMANCE_FAILED
1. Identify bottlenecks (database queries, missing indexes, no caching)
2. Return to Build phase to optimize
3. Re-run `/load-test`

#### Deploy DEPLOY_FAILED or AUTO_ROLLBACK
1. `/deployment-verification` triggered automatic rollback
2. Investigate failure cause from verification report
3. Create bug fix via `/intake`, re-enter pipeline

#### PR_BLOCKED
1. Fix quality gate failures
2. Re-run `/pr-creation`

### Step 4b: Extraction Assessment (Automatic, Post-Accept)

After Accept phase completes (APPROVED), check whether the codebase has grown to warrant service extraction:

1. Check the code-reviewer's output for **Extraction Candidate** flags (from the Review phase)
2. If extraction candidates were flagged with 3+ signals:
   - Report to user: "[Module] has crossed extraction thresholds. Recommend running `/service-extraction` after this feature ships."
   - If the user has previously configured auto-extraction (via `CLAUDE_AUTO_EXTRACT=true` in settings.json env), invoke `/service-extraction` automatically after Ship phase
   - Otherwise: add to pipeline output as a recommended follow-up action

This assessment is zero-cost — it reads the existing review output. No additional analysis needed.

### Step 5: Completion

When Ship phase returns PR_CREATED:
1. Update pipeline-state file: mark all phases as `completed`, record PR URL
2. Report PR URL to user
3. Output final pipeline summary with all agent contributions

## Status Reporting

At each phase transition, output a brief status line:

```
[Build] COMPLETE — BUILD_COMPLETE, 5 files changed, 23 tests green
[Review] PARALLEL DISPATCH — code-reviewer + security-engineer spawned...
[Review] COMPLETE — both APPROVE
[Verify] COMPLETE — VERIFIED (3/3 tiers pass)
[Test] COMPLETE — COVERED (87% on critical paths)
[Accept] COMPLETE — APPROVED
[Ship] COMPLETE — PR_CREATED: https://github.com/...
```

## Phase Output

```
Verdict: PIPELINE_COMPLETE / PIPELINE_IN_PROGRESS
Next: Report to user
Artifacts: [PR URL, all phase verdicts, agent summaries]
```

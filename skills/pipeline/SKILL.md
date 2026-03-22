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
| Feature (medium) | `/build-implementation` | Build → Review → Verify → Test → Accept → Ship |
| Feature (large) | `/build-implementation` | Build → Review → Verify → Test → Accept → Ship |
| Refactor | `/refactor` | Build → Review → Verify → Test → Accept → Ship |
| Bug Fix | `/bug-fix` | Build → Review → Verify → Test → Accept → Ship |
| Spike | `/tech-spike` | Spike only (no pipeline) |
| Planning | `/epic-breakdown` | Plan only (produces stories for future pipelines) |

**Pipeline scale tiers:**
- **Micro**: 1 file, less than 5 lines changed, no behavior change → Build + Review + Ship only
- **Small**: 1-3 files, isolated change → Build + Review + Verify + Ship
- **Medium/Large**: Full pipeline. No phase is skipped.

### Step 2: Create Pipeline State

**MANDATORY**: Create BOTH a structured pipeline state file AND a memory file at pipeline start.

**1. Pipeline state file** (persists across context compaction — primary):

```
pipeline-state/[feature-name]-pipeline.md
---
task_id: [feature-name]
phase: build
verdict: in_progress
timestamp: [ISO 8601]
---

## Pipeline: [feature name]
Started: [date]
Classification: [feature/refactor/bug]
Branch: [branch name]
Scale: [micro/small/medium/large]

## Phases
- Build: pending
- Review: pending
[...other phases...]
- Ship: pending

## Key Files
[list as discovered]
```

**2. Memory file** (secondary — for session continuity):

```
memory/pipeline_[feature_name].md
---
name: Pipeline State - [feature name]
description: In-progress pipeline for [feature], phase: Build, started [date]
type: project
---

## Pipeline: [feature name]
Started: [date]
Classification: [feature/refactor/bug]
Branch: [branch name]
Scale: [micro/small/medium/large]

## Phases
- Build: pending
- Review: pending
- Verify: pending
- Test: pending
- Accept: pending
- Ship: pending

## Completed Phases
(none yet)

## Outstanding
(none yet)

## Key Files
(none yet)
```

Update this file as each phase completes with verdict, artifacts, and agent summaries.

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

#### PR_BLOCKED
1. Fix quality gate failures
2. Re-run `/pr-creation`

### Step 5: Completion

When Ship phase returns PR_CREATED:
1. Update memory file: mark all phases as `completed`, record PR URL
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

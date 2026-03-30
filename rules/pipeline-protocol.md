# Pipeline Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/pipeline-orchestration.md`

## Skills Are Mandatory, Not Optional

When a pipeline phase has a corresponding skill, the skill's procedure MUST be executed. The dispatch mechanism depends on whether the phase agent writes files:

- **Read-only phases** (Test, Accept): Invoke via the Skill tool. The skill auto-forks to the correct read-only agent.
- **Write-capable phases** (Build, Verify Tier 3, QA gap-filling, review fix agents, scaffold): Spawn via the Agent tool with `isolation: "worktree"`. The agent prompt MUST include the instruction to read and execute the skill file at `~/.claude/skills/[name]/SKILL.md`. This ensures proper worktree isolation for parallel work.
- **Parallel phases** (Review): Unchanged. Use Parallel Dispatch Protocol.

**The skill IS the phase.** Whether invoked via Skill tool or read by an agent, the full skill procedure must be followed.

### Parallel Dispatch Exception

For phases in the Parallel Phase Map (see `rules/parallel-dispatch-protocol.md`), agents read and execute their own skill files instead of the orchestrator invoking skills via the Skill tool.

## Structured Pipeline State

Phase results are persisted as files in `~/.claude/pipeline-state/` to survive context compaction and enable inter-phase communication.

### File Convention
- **Naming**: `{task-id}-{phase}.md` e.g. `auth-feature-build.md`, `PROJ-123-review.md`
- **Lifecycle**: created by phase agent/skill, read by next phase, deleted after pipeline completes
- **Why files, not memory**: files survive context compaction intact; orchestrator memory does not

### Format
```markdown
---
task_id: {task-id}
phase: {build|review|verify|test|accept|ship}
verdict: {BUILD_COMPLETE|APPROVE|VERIFIED|COVERED|APPROVED|PR_CREATED|etc}
timestamp: {ISO 8601}
---

## Summary
{1-3 sentence phase outcome}

## Test Results
- Passed: {N}
- Failed: {N}
- Coverage: {N}%

## Key Findings
- {finding 1}
- {finding 2}

## Next Phase Input
{What the next phase needs to know from this phase}
```

### Orchestrator Responsibilities
- Check `pipeline-state/` for in-progress work before starting any new pipeline
- If in-progress state found: invoke `/pipeline-resume` to continue from the correct phase
- `pipeline-state/` is the single source of truth — do NOT dual-write to `memory/`
- Pass the previous phase's state file path to the next phase agent
- Delete all state files for a task after pipeline completion or abandonment
- Never leave stale state files — they confuse future pipeline runs

## Pre-flight Protocol (MANDATORY before any work begins)

1. **Check `pipeline-state/`** for in-progress pipelines before starting new work. If found, invoke `/pipeline-resume`
2. **Classify the work**: feature, refactor, bug fix, or tech spike
3. **Map to entry skill**: `/build-implementation`, `/refactor`, `/bug-fix`, or `/tech-spike`
3b. **Check for scaffolding needs**: if the task requires new API endpoints, schema changes, infrastructure, or observability, flag the appropriate utility skill (see pipeline SKILL.md Step 2b)
4. **Enumerate all pipeline phases** and the skill for each
5. **Write the phase plan** as a visible message to the user
6. **Execute phases in order**, invoking each skill via the Skill tool (or Parallel Dispatch for parallel phases)

## Phase Checklist (Summary)

Before advancing to any phase, verify the previous gate passed AND invoke the required skill.

- **Plan**: Design validation is a HARD GATE. No implementation begins without:
  1. Architect validates the approach (via `/epic-breakdown` or `/tech-spike`)
  2. At least one alternative approach considered and documented
  3. Product-reviewer + engineer validate the slices
  Use `/epic-breakdown`, `/estimation`, `/story-writing`, `/tech-spike` as needed
- **Build**: `/build-implementation` or `/refactor` or `/bug-fix` -- TDD, shape self-check
- **Review**: `/code-review` + `/security-review` via Parallel Dispatch -- both must APPROVE
- **Verify**: `/verify` -- check E2E trigger matrix (`rules/e2e-protocol.md`)
- **Test**: `/qa-test-strategy` -- all ACs covered, no gaps
- **Accept**: `/product-acceptance` -- APPROVED required
- **Ship**: `/pr-creation` -- PR with narrative, quality gate passes

## Review Protocol

### First Review
Dispatch code-reviewer + security-engineer in parallel (per parallel dispatch protocol).

Both reviewers use the same threshold: CRITICAL, HIGH, or MEDIUM findings trigger CHANGES_REQUESTED. LOW and INFO findings are included in the review output for the PR narrative but do not gate advancement.

### After CHANGES_REQUESTED
1. Spawn engineer (worktree) with the specific findings
2. Engineer fixes and commits
3. Merge the fix worktree
4. **Re-dispatch the raising reviewer is MANDATORY.** Do not skip re-review because the fix "looks right" — always re-dispatch.
5. Re-dispatch the raising reviewer (only) with: the original finding, the specific fix applied, and the file diff
6. **Targeted re-review**: Only the reviewer who raised the finding re-reviews
   - If code-reviewer raised findings and security-engineer APPROVED: only re-dispatch code-reviewer
   - If both raised findings: re-dispatch both, but each only re-reviews their own findings
- The re-reviewer checks ONLY the addressed findings plus immediate surrounding context
- They do NOT re-review the entire codebase (tests prove no regressions)
- Max 2 total rounds (initial + 1 re-review). If still not resolved, escalate to user.

### Fix Agent Review-Receiving Protocol

When spawning an engineer to address review findings, the prompt MUST include:

1. **Verify before implementing**: The fix agent must verify the reviewer's finding is valid before changing code. Read the cited code, understand the context, check if the concern applies.
2. **Technical correctness over compliance**: If the reviewer's suggestion would make the code worse, the fix agent reports back with a technical justification — it does not blindly implement.
3. **Actions over explanations**: Fix the code. Do not add comments explaining why the old code was wrong. The diff speaks.
4. **No compliance phrases in commits**: "Fixed per review feedback" is not a commit message. Describe WHAT changed and WHY.

### Why Single Re-Review
The build agent self-reviews before completion. Hooks enforce shape compliance. Tests prove correctness. A fix to a specific finding should not require a full re-audit — that is the assembly-line anti-pattern.

### Review Rules

1. **Never trust a fix agent's self-report.** Re-dispatch the raising reviewer independently after fix.
2. **Re-dispatch via Parallel Dispatch Protocol.** Each agent reads its own skill file. Do not paraphrase.
3. **Disputed findings require resolution, not dismissal.** The orchestrator cannot unilaterally dismiss.
4. **Track the loop.** Record verdicts, findings, fix plans, and re-review results.
5. **Maximum 2 total rounds.** Escalate to user if not resolved after 1 re-review.

## Async Review (Orchestrator Pattern)

When the orchestrator has other work available:
1. Spawn review agents in background (`run_in_background: true`)
2. Continue with the user on other tasks or stories
3. When review agents complete, resume the pipeline
4. This matches how real teams work: developer pushes PR, starts next story, reviewer reviews async

The orchestrator should NOT block waiting for review results when there is other work to do.

## Environment-Dependent Debugging Loop

When a built feature passes unit tests but fails in a real environment (device, staging, browser, external system), the pipeline enters a debugging loop:

### Entry criteria
- Feature was built and tests pass
- User reports failure with environment evidence (screenshot, logs, DOM dump, error output)
- The failure cannot be reproduced by unit tests alone

### Loop procedure
1. User reports failure with evidence
2. Orchestrator spawns agent (worktree) to fix the specific issue
3. Merge fix, push, user tests in environment
4. Repeat until user confirms working
5. Resume pipeline from **Review** phase on the cumulative diff

### Rules during the loop
- Pipeline gates (review, verify, test, accept) are **SUSPENDED** — they run once on the final working state
- Each fix still goes through an **agent** (orchestrator NEVER edits source files directly)
- Each fix is **committed** with a descriptive message (audit trail preserved)
- Maximum **5 iterations** — then escalate to user with options
- The orchestrator coordinates and delegates, it does not write code — especially under time pressure

### Why this exists
Environment-dependent testing (mobile devices, WebView integration, staging deploys) inherently requires test-fix-retest cycles that unit tests cannot validate. Running full pipeline gates on each intermediate fix wastes effort on throwaway states. The gates add value on the final working state, not on each debugging step.

## Enforcement

> **IRON LAW: NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED.**

- If you catch yourself about to use Write or Edit on a source file, STOP
- If you catch yourself about to skip a skill invocation, STOP
- If you catch yourself about to spawn a write-capable agent WITHOUT `isolation: "worktree"`, STOP. If you catch yourself spawning an agent without referencing the skill file, STOP.
- The user saying "just fix it quickly" is not an excuse to bypass process
- The pipeline exists to catch mistakes. Every shortcut is a missed catch.

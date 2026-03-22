# Pipeline Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/pipeline-orchestration.md`

## Skills Are Mandatory, Not Optional

When a pipeline phase has a corresponding skill, invoking it via the Skill tool is a HARD REQUIREMENT. Do not manually perform what a skill is designed to do.

**The skill IS the phase.** Spawning the right agent type with a detailed prompt is NOT the same as invoking the skill.

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
- Pass the previous phase's state file path to the next phase agent
- Delete all state files for a task after pipeline completion or abandonment
- Never leave stale state files — they confuse future pipeline runs

## Pre-flight Protocol (MANDATORY before any work begins)

1. **Check `pipeline-state/`** for in-progress pipelines before starting new work
2. **Classify the work**: feature, refactor, bug fix, or tech spike
3. **Map to entry skill**: `/build-implementation`, `/refactor`, `/bug-fix`, or `/tech-spike`
4. **Enumerate all pipeline phases** and the skill for each
5. **Write the phase plan** as a visible message to the user
6. **Execute phases in order**, invoking each skill via the Skill tool (or Parallel Dispatch for parallel phases)

## Phase Checklist (Summary)

Before advancing to any phase, verify the previous gate passed AND invoke the required skill.

- **Plan**: `/epic-breakdown`, `/estimation`, `/story-writing`, `/tech-spike` as needed
- **Build**: `/build-implementation` or `/refactor` or `/bug-fix` -- TDD, shape self-check
- **Review**: `/code-review` + `/security-review` via Parallel Dispatch -- both must APPROVE
- **Verify**: `/verify` -- check E2E trigger matrix (`rules/e2e-protocol.md`)
- **Test**: `/qa-test-strategy` -- all ACs covered, no gaps
- **Accept**: `/product-acceptance` -- APPROVED required
- **Ship**: `/pr-creation` -- PR with narrative, quality gate passes

## Review Protocol

### First Review
Dispatch code-reviewer + security-engineer in parallel (per parallel dispatch protocol).

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

## Enforcement

- If you catch yourself about to use Write or Edit on a source file, STOP
- If you catch yourself about to skip a skill invocation, STOP
- If you catch yourself about to spawn an agent directly when a skill exists for that phase, STOP
- The user saying "just fix it quickly" is not an excuse to bypass process
- The pipeline exists to catch mistakes. Every shortcut is a missed catch.

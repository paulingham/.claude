# Pipeline Orchestration (Orchestrator-Only)

Extracted from `rules/pipeline-protocol.md`. Agents do not need this content.

## Pipeline State Tracking

Pipeline state is tracked using `pipeline-state/[feature-name]-pipeline.md` files. Each pipeline run creates a state file with YAML frontmatter (task_id, phase, verdict, timestamp, scale, branch) plus phase status, verdicts, artifacts, and agent summaries. This is the single source of truth — do NOT dual-write to `memory/`.

### State File Structure

```markdown
---
name: Pipeline State - [feature name]
description: In-progress pipeline for [feature], phase: [current], started [date]
type: project
---

## Pipeline: [feature name]
Started: [date]
Classification: [feature/refactor/bug]
Branch: [branch name]
Scale: [micro/small/medium/large]

## Phases
- Build: [pending/in_progress/completed] -- [verdict if completed]
- Review: [pending/in_progress/completed] -- [verdict if completed]
- Verify: [pending/in_progress/completed] -- [verdict if completed]
- Test: [pending/in_progress/completed] -- [verdict if completed]
- Accept: [pending/in_progress/completed] -- [verdict if completed]
- Ship: [pending/in_progress/completed] -- [verdict if completed]

## Completed Phases
- Build: BUILD_COMPLETE -- [files], [test count] tests
- Review: APPROVE -- [summary of findings addressed]

## Current Phase
- Verify: IN_PROGRESS -- Tier 1 passed, Tier 2 pending

## Outstanding
- [Any findings to address]
- [Any conditions from prior phases]

## Key Files
- [list of files changed in this pipeline]

## Agent Summaries
- [agent type]: [2-3 sentence summary]

## Decision Record
[From build agent — design choices with rationale. See build-implementation skill.]

## Context for Next Phase
[Structured handoff: uncertainty flags, areas needing focus, TDD audit summary.
Each phase writes its own section — the next phase reads it.]
```

### Context Bundles (Phase Handoff Convention)

Each phase writes a `## Context for Next Phase` section in the pipeline state file. This is how agents communicate intent, not just artifacts:

| Source Phase | Target Phase | Key Context |
|---|---|---|
| Plan | Build | Design rationale, rejected alternatives, risk areas, test strategy |
| Build | Review | Decision records, uncertainty flags, TDD audit summary, instincts applied |
| Review | Fix-engineer | Finding context ("fix X because Y, consider Z"), decision record responses |
| Fix | Re-reviewer | What changed, why original was chosen, why fix is correct |
| Verify | Ship | Coverage map, confidence levels per area |

The orchestrator includes the relevant context section when spawning the next phase's agents. This replaces the previous pattern of passing only git diff + verdict string.

### State Transitions

- `pending` -> `in_progress`: Phase skill invoked, agents dispatched, or teammates spawned
- `in_progress` -> `completed`: Phase verdict is success (all teammates report complete)
- `in_progress` -> stays `in_progress`: Recovery loop (CHANGES_REQUESTED, GAPS_FOUND, etc.)

### Team State

The pipeline team's state is tracked alongside the pipeline state:

```
## Team: pipeline-{task-id}
Active teammates: [list of currently spawned teammates]
Phase: [current team phase]
```

When teammates go idle after completing tasks, the orchestrator checks `TaskList` for the team to determine if the phase is complete (all tasks done) before advancing.

### Updating State

After each phase completes, update the memory file with:
- Phase status changed to `completed`
- Verdict recorded
- Artifacts listed (files changed/created)
- Agent summary appended
- Current phase pointer advanced

## Conversation Continuity

### During Conversation
Pipeline state lives in `pipeline-state/[feature-name]-pipeline.md`. Each phase update writes verdicts, artifacts, and agent summaries to this file.

### Before Context Compression
When context is approaching limits:
1. Verify pipeline state is saved in `pipeline-state/[feature-name]-pipeline.md`
2. Ensure it includes: current phase, all verdicts so far, outstanding findings, key file paths
3. The pipeline-state file IS the state — use `/pipeline-resume` to recover on new session

### On New Conversation Start
1. Check memory for `pipeline_*.md` files
2. If found, offer to resume: "Pipeline in progress for [feature]. Phase: [current]. Resume?"
3. If user confirms, read the memory file and continue from the current phase

### Phase Handoff Documents

At each phase transition, the completing skill produces a structured output (see Phase Output in each skill). This output contains:
- **Verdict**: The gate result
- **Next**: Which skill to invoke next
- **Artifacts**: Files changed/created
- **Agent summaries**: 2-3 sentence contribution from each agent

This output is recorded in the pipeline memory file and is available to the next phase.

## Progress Reporting

### Phase Transition Reports

At each pipeline phase transition, output a brief status line. Do not ask for input -- just inform.

```
[Phase] STATUS -- verdict, key metric
```

Examples:

```
[Build] TEAM PHASE -- 2 engineers spawned (backend-engineer, frontend-engineer)
[Build] COMPLETE -- BUILD_COMPLETE, 6 files created, 23 tests green, engineers shut down
[Review] TEAM PHASE -- code-reviewer + security-engineer spawned
[Review] CHANGES_REQUESTED -- 3 findings (1 critical, 2 suggestions). Spawning fix-engineer...
[Review] RE-REVIEW -- re-assigned to code-reviewer (context preserved)
[Review] COMPLETE -- both APPROVE, reviewers shut down
[Final Gate] TEAM PHASE -- verifier + test-analyst + product-reviewer spawned
[Final Gate] COMPLETE -- VERIFIED + COVERED + APPROVED, all shut down
[Ship] COMPLETE -- PR_CREATED: https://github.com/org/repo/pull/42
```

### Recovery Loop Reports

When in a recovery loop (CHANGES_REQUESTED, GAPS_FOUND, etc.):

```
[Review] RE-REVIEW 2/2 -- fixing: function body > 5 lines in useNavigationHandler.ts
[Review] RE-DISPATCHING -- targeted re-review of raising reviewer(s) after fix...
```

### Milestone Reports

At natural milestones (after Build, after Review, after all phases):

```
Pipeline Progress: 4/6 phases complete
  Build:  BUILD_COMPLETE (6 files, 23 tests)
  Review: APPROVE (both reviewers)
  Verify: VERIFIED (3/3 tiers)
  Test:   COVERED (92%)
  Accept: [pending]
  Ship:   [pending]
```

### When NOT to Report

- Do not report on individual file reads/writes
- Do not report on internal agent decisions
- Do not ask for confirmation before standard phase transitions
- Do not output full test results -- just pass/fail counts

## Review Findings Log

After each review round, record findings for attribution and re-review tracking:

| ID | Reviewer | Severity | File:Line | Description | Status |
|----|----------|----------|-----------|-------------|--------|
| F1 | code-reviewer | critical | helpers.ts:43 | Missing try/catch | FIXED (commit abc) |
| F2 | security-engineer | medium | state.ts:22 | Initial state race | DEFERRED |

On re-review, dispatch ONLY the reviewer who raised unresolved findings.
Each reviewer re-reviews ONLY their own findings, not the full diff.

## Async Review

When the orchestrator has other work available (e.g., multiple stories in a pipeline):
1. Review teammates work in their tmux panes -- they're visible, no background flag needed
2. Continue with the user on other tasks or stories
3. When reviewers mark tasks complete and go idle, resume the pipeline
4. Review is max 2 total rounds (initial + 1 targeted re-review), not 3 full re-audits

The orchestrator should NOT block waiting for review results when there is other work to do.

## Anti-Patterns (from real incidents)

### "I have a detailed plan, I'll just spawn agents directly"
**What happens:** The orchestrator has a plan with specific agent instructions, so it spawns frontend-engineer agents with detailed prompts, bypassing `/build-implementation` or `/refactor`. The code works, tests pass, but: no characterization tests were written (refactor safety), no RED-GREEN-REFACTOR audit trail (TDD), no structured verification, no formal gate closure.
**Fix:** Invoke the skill. The skill structures the work. The plan informs the skill, it does not replace it.

### "It's just a refactor, Verify/Test/Accept don't apply"
**What happens:** The orchestrator decides that a "pure structural refactor" doesn't need `/verify` (no new boundaries to contract-test), `/qa-test-strategy` (existing tests pass), or `/product-acceptance` (no user-facing change). Three phases get skipped.
**Why it's wrong:** `/verify` would catch that new extraction boundaries (hooks, helpers) have no dedicated tests -- mutation testing would reveal untested code. `/qa-test-strategy` would flag coverage gaps. `/product-acceptance` would verify the refactor didn't change behavior.
**Fix:** Every phase applies to every work type. The scope of each phase scales down for small tasks, but no phase is skipped.

### "CHANGES_REQUESTED, fixed it, moving on"
**What happens:** Reviewers return CHANGES_REQUESTED. The orchestrator spawns an engineer to fix, trusts the fix agent's self-report, and moves on without re-dispatching the reviewers. This means no independent verification that the fix is correct and the gate was never formally closed.
**Fix:** After fix, targeted re-review: re-dispatch only the reviewer(s) who raised findings. They check the addressed findings plus immediate surrounding context. Max 2 total rounds (initial + 1 re-review). Async when other work is available.
**Incident:** This happened on 2026-03-17 and is the reason the review protocol exists.

### "I'll spawn the reviewer agent directly -- same thing as the skill"
**What happens:** The orchestrator spawns a `code-reviewer` agent with a prompt describing what to review, bypassing `/code-review`. The review happens but without the skill's structured checklist, severity framework, and verdict format.
**Why it's wrong:** Skills embed protocols. The `/code-review` skill has a specific checklist (shape, DRY, SRP, test quality, error handling). Direct agent spawning lets the orchestrator define the review scope, which may omit checks.
**Fix:** Use Parallel Dispatch Protocol. Agents read and execute the skill file themselves. The prompt must include the skill file path (`~/.claude/skills/code-review/SKILL.md`), not a paraphrased version of the checklist.

### Continuity Anti-Patterns

- **Never start a new pipeline without checking for in-progress ones.** One pipeline at a time per branch.
- **Never discard pipeline state.** If the user wants to abandon, explicitly delete the memory file.
- **Never assume prior context.** Always read state from the memory file, not from "I remember from last time."

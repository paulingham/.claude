# Pipeline Protocol

Consolidates: pipeline enforcement, pipeline state, review loop, progress reporting, conversation continuity.

## Skills Are Mandatory, Not Optional

When a pipeline phase has a corresponding skill, invoking it via the Skill tool is a HARD REQUIREMENT. Do not manually perform what a skill is designed to do.

**The skill IS the phase.** Spawning the right agent type with a detailed prompt is NOT the same as invoking the skill. Skills contain embedded protocols, checklists, and audit trail requirements that direct agent spawning bypasses.

### Parallel Dispatch Exception

For phases in the Parallel Phase Map (see `rules/parallel-dispatch-protocol.md`), agents read and execute their own skill files instead of the orchestrator invoking skills via the Skill tool. This is the ONLY exception to "invoke via Skill tool." The agents still execute the full skill procedure -- the dispatch mechanism changes, not the protocol.

## Pre-flight Protocol (MANDATORY before any work begins)

Before writing any code, spawning any agent, or invoking any skill, the orchestrator MUST:

1. **Classify the work**: feature, refactor, bug fix, or tech spike
2. **Map to entry skill**: `/build-implementation`, `/refactor`, `/bug-fix`, or `/tech-spike`
3. **Enumerate all pipeline phases** that will apply and the skill for each
4. **Write the phase plan** as a visible message to the user:
   ```
   Pipeline for this [refactor]:
   - Build: /refactor (entry skill)
   - Review: /code-review + /security-review (parallel dispatch)
   - Verify: /verify
   - Test: /qa-test-strategy
   - Accept: /product-acceptance
   - Ship: /pr-creation (if requested)
   ```
5. **Execute phases in order**, invoking each skill via the Skill tool (or Parallel Dispatch for parallel phases)

If you skip this pre-flight, you WILL drift into the bypass pattern -- spawning agents directly because "I know what to do."

## Phase Checklist

Before advancing to any phase, verify the previous gate passed AND invoke the required skill.

### New Project
- [ ] Check for `.claude/CLAUDE.md` at project root
- [ ] If missing: invoke `/project-setup` via Skill tool -- do NOT manually create it
- [ ] Read the generated CLAUDE.md and confirm no conflicts

### Plan Phase
- [ ] If epic/feature: invoke `/epic-breakdown` via Skill tool
- [ ] If sizing needed: invoke `/estimation` via Skill tool
- [ ] If single story needed: invoke `/story-writing` via Skill tool
- [ ] If unknowns exist: invoke `/tech-spike` via Skill tool
- [ ] Gate: product-reviewer validates scope, engineer confirms feasibility

### Build Phase
- [ ] Invoke `/build-implementation` or `/refactor` or `/bug-fix` via Skill tool -- the skill spawns agents, NOT the orchestrator
- [ ] Engineer follows incremental TDD protocol (one test at a time, RED -> GREEN -> REFACTOR)
- [ ] Shape self-check after every file: functions <= 5 lines, files <= 50 lines, CC <= 5, nesting <= 2
- [ ] No bulk test-then-implement pattern -- each cycle produces one test and minimum code
- [ ] Gate: tests green, TypeScript clean, all shape constraints met

### Review Phase
- [ ] Dispatch `/code-review` + `/security-review` via Parallel Dispatch Protocol (see `rules/parallel-dispatch-protocol.md`)
- [ ] Spawn code-reviewer + security-engineer in a single message, each reading their own skill file
- [ ] Gate: both APPROVE -- if CHANGES_REQUESTED, spawn engineer to fix, then RE-DISPATCH BOTH reviewers (max 3 iterations)
- [ ] The review loop is not closed until both skills return APPROVE on the fixed code

### Verify Phase
- [ ] Invoke `/verify` via Skill tool -- do NOT manually run verification
- [ ] Check E2E trigger matrix (`rules/e2e-protocol.md`) -- if changed files match, Tier 4 E2E runs as part of `/verify`
- [ ] Gate: verification report says VERIFIED or VERIFIED_WITH_SKIP
- [ ] If VERIFIED_WITH_SKIP: E2E was skipped due to missing prerequisites -- product-reviewer must acknowledge in Accept phase

### Test Phase
- [ ] Invoke `/qa-test-strategy` via Skill tool
- [ ] Gate: all ACs have tests, no gaps identified, coverage report complete

### Accept Phase
- [ ] Invoke `/product-acceptance` via Skill tool
- [ ] Gate: APPROVED -- if APPROVED WITH CONDITIONS, fix conditions first

### Ship Phase
- [ ] Invoke `/pr-creation` via Skill tool -- do NOT manually create PRs
- [ ] Gate: PR created with narrative, quality gate hook passes

### Bug Fixes
- [ ] Invoke `/bug-fix` via Skill tool -- do NOT manually fix bugs

### Refactoring
- [ ] Invoke `/refactor` via Skill tool -- do NOT manually refactor

## Review Loop

The review phase is a loop, not a one-shot:

```
Parallel Dispatch (code-reviewer + security-engineer, each reading their skill file)
  -> Both APPROVE? -> proceed to Verify
  -> CHANGES_REQUESTED? -> spawn engineer to fix -> RE-DISPATCH BOTH reviewers -> repeat
  -> Max 3 iterations -> escalate to user
```

The loop only terminates when BOTH reviewers return APPROVE on the same codebase, or escalation occurs after 3 iterations.

### Review Loop Rules

1. **Never trust a fix agent's self-report.** After a fix, the code-reviewer and security-engineer must independently verify the fix is correct. Self-assessment is not a gate.

2. **Re-dispatch via Parallel Dispatch Protocol.** After a fix, re-dispatch both reviewers using `rules/parallel-dispatch-protocol.md`. Each agent reads its own skill file. Do not paraphrase the skill content in the agent prompt.

3. **Re-review the full scope**, not just the fix. The fix may have introduced new issues. The reviewers examine the complete changed codebase, not just the delta from the fix.

4. **Disputed findings require resolution, not dismissal.** If a finding is disputed (e.g., "this is pre-existing, not a regression"), the reviewer must acknowledge and accept the dispute, or the finding stands. The orchestrator cannot unilaterally dismiss a finding.

5. **Track the loop.** After each review round, note: what was the verdict, what findings need fixing, and what the fix plan is. After the fix, note: what was fixed and what's being re-reviewed. This creates an audit trail.

6. **Maximum 3 iterations.** If both reviewers have not returned APPROVE after 3 rounds of fix-and-re-dispatch, escalate to the user. Infinite review loops waste context and indicate a deeper problem (ambiguous requirements, architectural mismatch, or skill gap).

## Pipeline State Tracking

Pipeline state is tracked using `memory/pipeline_[feature_name].md` files. Each pipeline run creates a memory file with phase status, verdicts, artifacts, and agent summaries.

### Memory File Structure

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
```

### State Transitions

- `pending` -> `in_progress`: Phase skill invoked or agents dispatched
- `in_progress` -> `completed`: Phase verdict is success
- `in_progress` -> stays `in_progress`: Recovery loop (CHANGES_REQUESTED, GAPS_FOUND, etc.)

### Updating State

After each phase completes, update the memory file with:
- Phase status changed to `completed`
- Verdict recorded
- Artifacts listed (files changed/created)
- Agent summary appended
- Current phase pointer advanced

## Conversation Continuity

### During Conversation
Pipeline state lives in memory files (`memory/pipeline_[feature].md`). Each phase update writes verdicts, artifacts, and agent summaries to the file.

### Before Context Compression
When context is approaching limits:
1. Verify pipeline state is saved in the memory file: `memory/pipeline_[feature].md`
2. Ensure it includes: current phase, all verdicts so far, outstanding findings, key file paths
3. The memory file IS the state -- no separate backup needed

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
[Build] COMPLETE -- BUILD_COMPLETE, 6 files created, 23 tests green
[Review] PARALLEL DISPATCH -- code-reviewer + security-engineer spawned
[Review] CHANGES_REQUESTED -- 3 findings (1 critical, 2 suggestions). Spawning fix...
[Review] COMPLETE -- both APPROVE on second round
[Verify] COMPLETE -- VERIFIED (Tier 1: PASS, Tier 2: PASS, Tier 3: N/A)
[Test] COMPLETE -- COVERED (92% on critical paths, 0 gaps)
[Accept] COMPLETE -- APPROVED
[Ship] COMPLETE -- PR_CREATED: https://github.com/org/repo/pull/42
```

### Recovery Loop Reports

When in a recovery loop (CHANGES_REQUESTED, GAPS_FOUND, etc.):

```
[Review] LOOP 2/3 -- fixing: function body > 5 lines in useNavigationHandler.ts
[Review] RE-DISPATCHING -- code-reviewer + security-engineer after fix...
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

## Enforcement

- If you catch yourself about to use Write or Edit on a source file, STOP
- If you catch yourself about to skip a skill invocation, STOP
- If you catch yourself about to spawn an agent directly when a skill exists for that phase, STOP
- If the user says "just fix it quickly", delegate to an agent -- speed is not an excuse to bypass process
- The pipeline exists to catch mistakes. Every shortcut is a missed catch.

## Anti-Patterns (from real incidents)

### "I have a detailed plan, I'll just spawn agents directly"
**What happens:** The orchestrator has a plan with specific agent instructions, so it spawns frontend-engineer agents with detailed prompts, bypassing `/build-implementation` or `/refactor`. The code works, tests pass, but: no characterization tests were written (refactor safety), no RED-GREEN-REFACTOR audit trail (TDD), no structured verification, no formal gate closure.
**Fix:** Invoke the skill. The skill structures the work. The plan informs the skill, it does not replace it.

### "It's just a refactor, Verify/Test/Accept don't apply"
**What happens:** The orchestrator decides that a "pure structural refactor" doesn't need `/verify` (no new boundaries to contract-test), `/qa-test-strategy` (existing tests pass), or `/product-acceptance` (no user-facing change). Three phases get skipped.
**Why it's wrong:** `/verify` would catch that new extraction boundaries (hooks, helpers) have no dedicated tests -- mutation testing would reveal untested code. `/qa-test-strategy` would flag coverage gaps. `/product-acceptance` would verify the refactor didn't change behavior.
**Fix:** Every phase applies to every work type. The scope of each phase scales down for small tasks, but no phase is skipped.

### "CHANGES_REQUESTED, fixed it, moving on"
**What happens:** Reviewers return CHANGES_REQUESTED. The orchestrator spawns an engineer to fix, trusts the fix agent's self-report, and moves on without re-dispatching the reviewers. This means no independent verification that the fix is correct, no check for new issues introduced by the fix, and the gate was never formally closed.
**Fix:** After fix, re-dispatch both reviewers via Parallel Dispatch Protocol. The loop is: dispatch -> verdict -> fix -> dispatch -> verdict. It only ends at APPROVE.
**Incident:** This happened on 2026-03-17 and is the reason the review loop rule exists.

### "I'll spawn the reviewer agent directly -- same thing as the skill"
**What happens:** The orchestrator spawns a `code-reviewer` agent with a prompt describing what to review, bypassing `/code-review`. The review happens but without the skill's structured checklist, severity framework, and verdict format.
**Why it's wrong:** Skills embed protocols. The `/code-review` skill has a specific checklist (shape, DRY, SRP, test quality, error handling). Direct agent spawning lets the orchestrator define the review scope, which may omit checks.
**Fix:** Use Parallel Dispatch Protocol. Agents read and execute the skill file themselves. The prompt must include the skill file path (`~/.claude/skills/code-review/SKILL.md`), not a paraphrased version of the checklist.

### Continuity Anti-Patterns

- **Never start a new pipeline without checking for in-progress ones.** One pipeline at a time per branch.
- **Never discard pipeline state.** If the user wants to abandon, explicitly delete the memory file.
- **Never assume prior context.** Always read state from the memory file, not from "I remember from last time."

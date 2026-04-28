# Pipeline Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/pipeline-orchestration.md`

## Skills Are Mandatory, Not Optional

When a pipeline phase has a corresponding skill, the skill's procedure MUST be executed. The dispatch mechanism depends on the phase:

- **Subagent phases** (Plan, Ship, Deploy, single-slice Build): Invoke via Skill tool or Agent tool with `isolation: "worktree"`. Ephemeral, no visibility.
- **Team phases** (multi-slice Build, Review, Final Gate): Spawn teammates into the pipeline team via Agent tool with `team_name`. Visible in tmux panes. See `rules/parallel-dispatch-protocol.md`.
- **Single-slice Build**: Use subagent with `isolation: "worktree"` (team overhead not justified for one engineer).

**The skill IS the phase.** Whether invoked via Skill tool, read by a subagent, or read by a teammate, the full skill procedure must be followed.

### Team Dispatch

For phases in the Team Phases table (see `rules/parallel-dispatch-protocol.md`), teammates are spawned into the pipeline team and read their own skill files. The orchestrator creates tasks and assigns them. See `orchestrator/parallel-dispatch-details.md` for exact dispatch procedure.

## Best-of-N Build Dispatch

Best-of-N Build dispatch fires when `/intake` tags the task with `bestofn: true`. The gate is `critical OR (task_class == "feature" AND Budget >= 5)` — Best-of-N is therefore the default for non-trivial features as well as for any critical task. The persisted `bestofn` flag (written by intake Step 2d-bis to the intake state file, mirrored into the pipeline state by `/pipeline` Step 2) drives the dispatch and survives context compaction; `/pipeline-resume` reads the flag rather than recomputing it. Implementation is a Team dispatch variant (see `rules/parallel-dispatch-protocol.md` § Best-of-N Build Team) — N candidate engineers run in parallel worktrees, each on a different model, and a single code-reviewer selects the winner. The winner still faces the normal Review → Final Gate → Ship gates; scoring picks *which* candidate faces those gates, it does not substitute for them. Cost is roughly 2-3x a standard build; justified on high-stakes slices and non-trivial features where a quality uplift beats the extra spend. On failure, the pipeline falls back to standard Build dispatch — it never halts and never asks the user.

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
phase: {plan|build|review|verify|test|accept|ship}
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
- Also delete `pipeline-state/{task-id}-approval.token` at Reflect step 6d alongside `{task-id}-*.md` state files. Stale APPROVED tokens from crashed pipelines would silently pre-authorize future pipelines that reuse the same task-id.
- Never leave stale state files — they confuse future pipeline runs

## Pre-flight Protocol (MANDATORY before any work begins)

1. **Check `pipeline-state/`** for in-progress pipelines before starting new work. If found, invoke `/pipeline-resume`
2. **Classify the work**: feature, refactor, bug fix, or tech spike
3. **Map to entry skill**: `/build-implementation`, `/refactor`, `/bug-fix`, or `/tech-spike`
3b. **Check for scaffolding needs**: if the task requires new API endpoints, schema changes, infrastructure, or observability, flag the appropriate utility skill (see pipeline SKILL.md Step 2b)
4. **Enumerate all pipeline phases** and the skill for each
5. **Determine dispatch mode**: single-slice (subagents) or multi-slice/multi-domain (team)
6. **Create pipeline team**: `TeamCreate("pipeline-{task-id}")` -- always, even for single-slice (the team hosts review + final gate teammates)
6b. **Create pipeline scratchpad**: `mkdir -p pipeline-state/{task-id}-scratchpad/` (see `rules/autonomous-intelligence.md`)
6c. **Load session memory**: Read `session-memory/{project-hash}/notes.md` if it exists. Create from template if first pipeline in this project
7. **Write the phase plan** as a visible message to the user
8. **Execute phases in order**, spawning teammates for team phases, subagents for subagent phases. Inject session memory + scratchpad findings into every agent prompt (see `rules/autonomous-intelligence.md` § Agent Spawn)

## Phase Checklist (Summary)

Before advancing to any phase, verify the previous gate passed AND invoke the required skill.

- **Plan**: Design validation is a HARD GATE (ALL pipelines). No implementation begins without:
  1. Architect produces plan with `## Alternatives Considered` (minimum 2 genuine approaches)
  2. Interactive mode: user approves the plan
  3. Autonomous mode: product-reviewer + software-engineer both APPROVE the plan
  4. Maximum 2 rounds of revision before escalation
  5. Gate tracked in pipeline state as `Plan Validation` phase
  Use `/epic-breakdown`, `/estimation`, `/story-writing`, `/tech-spike` as needed
- **Build**: `/build-implementation` or `/refactor` or `/bug-fix` -- TDD, shape self-check
- **Review**: `/code-review` + `/security-review` as team (tmux visible) -- both must APPROVE
- **Final Gate** (Verify + Test + Accept + Patch Critique as team, parallel):
  - `/verify` -- check E2E trigger matrix (`rules/e2e-protocol.md`)
  - `/qa-test-strategy` -- all ACs covered, no gaps
  - `/product-acceptance` -- APPROVED required
  - `/patch-critique` -- PATCH_APPROVED required (rubric: tests cover change, diff minimal vs spec, no obvious regressions, no incidental refactor). PATCH_REJECTED returns to fix-engineer (no user escalation per § In-Cycle Fix Rule).
- **Ship**: `/pr-creation` -- PR with narrative, quality gate passes. Requires `pipeline-state/{task-id}-approval.token` with verdict `APPROVED` or `APPROVED_WITH_CONDITIONS` (written by `/product-acceptance`). Gate checked at `/pr-creation` Step 0 via `hooks/_lib/approval-token.sh`. Missing or REJECTED token → `PR_BLOCKED`.

#### `gh pr create` Bypass (Residual Risk, Out of Scope)

Direct `gh pr create` invocations via Bash bypass the `/pr-creation` skill and therefore bypass the approval token gate. The existing `main-branch-guard.sh` PreToolUse hook already enforces the worktree pattern for `gh pr create`, but does not check the approval token. A future `hooks/pr-approval-guard.sh` hook could extend coverage to direct Bash invocations — tracked as a follow-up, not in this wave.

## Review Protocol

### First Review
Spawn code-reviewer + security-engineer as teammates in the pipeline team (per parallel dispatch protocol). Both work simultaneously, visible in tmux panes.

Both reviewers use the same threshold: CRITICAL, HIGH, or MEDIUM findings trigger CHANGES_REQUESTED. LOW and INFO findings are included in the review output for the PR narrative but do not gate advancement.

### In-Cycle Fix Rule (IRON LAW)

> **Findings surfaced during review are fixed IN THIS PIPELINE. Never filed as follow-ups. Never surfaced as questions to the user.**

This applies to findings from code-reviewer, security-engineer, product-reviewer, qa-engineer, verify phase, AND build-phase scratchpad warnings that indicate the shipped change is incomplete or leaves adjacent documented behavior broken.

- **No follow-up tickets** for defects the current change exposes, leaves broken, or makes misleading. Follow-ups are ONLY for genuinely orthogonal work (different module, different contract, different user journey).
- **No "ship as-is + file ticket"** compromises. The pipeline does not ship known-incomplete fixes.
- **No questions to the user** asking whether to expand scope. The pipeline decides autonomously: dispatch fix-engineer, roll the fix into the current branch family, re-run targeted review, then ship.
- **"Minimal scope" / "narrow fix" user directives** constrain *approach* (don't reorganize, don't refactor unrelated code), not *coverage* (ignore defects the fix exposes). Read user constraints literally.
- **Escalate to the user ONLY if** the required fix is architecturally large (cross-service, new module, >~100 LOC) OR outside the current task's layer. In that case HALT the pipeline — do not ship the incomplete fix.

Round counting: expanding scope to fix an in-cycle finding does NOT reset the review-round counter, but a clean re-review on the combined diff is still required before ship.

### After CHANGES_REQUESTED
1. Spawn fix-engineer into the same pipeline team with the specific findings
2. Fix-engineer fixes and commits
3. Shut down fix-engineer, merge the fix branch
4. **Re-assign to the raising reviewer is MANDATORY.** The reviewer is still alive in the team with full context. Do not skip re-review because the fix "looks right."
5. `SendMessage` to the raising reviewer with: the original finding, the specific fix applied, and the file diff
6. **Targeted re-review**: Only the reviewer who raised the finding re-reviews
   - If code-reviewer raised findings and security-engineer APPROVED: only message code-reviewer
   - If both raised findings: message both, but each only re-reviews their own findings
- The re-reviewer checks ONLY the addressed findings plus immediate surrounding context
- They do NOT re-review the entire codebase (tests prove no regressions)
- Max 2 total rounds (initial + 1 re-review). If still not resolved, escalate to user.
- After both APPROVE: shut down both reviewers.

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
1. Review teammates work in their tmux panes -- no background flag needed, they're visible
2. Continue with the user on other tasks or stories
3. When reviewers mark tasks complete and go idle, resume the pipeline
4. This matches how real teams work: developer pushes PR, starts next story, reviewer reviews async

The orchestrator should NOT block waiting for review results when there is other work to do.

## Environment-Dependent Debugging Loop

When a built feature passes unit tests but fails in a real environment (device, staging, browser, external system), the pipeline enters a debugging loop:

### Persistent State
When entering the debugging loop, invoke `/debug` to create persistent state in `pipeline-state/{task-id}-debug.md`. This ensures hypotheses, elimination results, and fix attempts survive context compaction and session boundaries.

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
- If you catch yourself about to spawn a write-capable subagent WITHOUT `isolation: "worktree"`, STOP (team teammates manage their own branches)
- If you catch yourself spawning an agent or teammate without referencing the skill file, STOP
- If you catch yourself keeping teammates alive across phases (idle token burn), STOP -- shut them down
- The user saying "just fix it quickly" is not an excuse to bypass process
- The pipeline exists to catch mistakes. Every shortcut is a missed catch.

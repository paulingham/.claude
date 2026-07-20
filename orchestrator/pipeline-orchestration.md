# Pipeline Orchestration (Orchestrator-Only)

Extracted from `protocols/pipeline-protocol.md`. Agents do not need this content.

## Pipeline State Tracking

Pipeline state is tracked using `$state_dir/[feature-name]/pipeline.md` files (workstream variant: `$state_dir/workstreams/{ws}/[feature-name]/pipeline.md`). Each pipeline run creates a state file with YAML frontmatter (task_id, phase, verdict, timestamp, scale, branch) plus phase status, verdicts, artifacts, and agent summaries. This is the single source of truth — do NOT dual-write to `memory/`.

During the DUAL_PATH soak (see `protocols/pipeline-protocol.md` § Structured Pipeline State), the legacy flat form `$state_dir/[feature-name]-pipeline.md` is still tolerated by readers but never used for new code. Path resolution always goes through `hooks/_lib/pipeline_state_paths.py` (or `pipeline-state-paths.sh` from bash).

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
| Plan | Plan Validation | Full architect output including alternatives, slices, ACs |
| Plan Validation | Build | Approved plan, challenger endorsements, risk areas flagged |
| Plan Validation | Plan (re-plan) | Combined challenger feedback, specific rejection reasons |
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

### Detecting Build Completion

A write-capable build agent's prose report can stall before it is ever emitted, leaving the orchestrator with no completion signal to parse. The orchestrator does NOT wait on or parse agent prose to decide `in_progress` -> `completed` for a Build phase. Instead:

1. **Read the file FIRST.** Before touching any prose output, call `hooks/_lib/build_result_reader.py::read_build_result(state_dir_abs, task_id)`. This is the machine-readable source of truth (see `skills/build-implementation/SKILL.md` § Completion Signal (SSOT)).
2. **COMPLETE -> advance.** `status == "COMPLETE"` means the build agent's last durable action succeeded — advance the phase to `completed` and proceed to the next phase using the returned `branch`/`head_sha`.
3. **MISSING / CORRUPT / absent -> branch-recovery, never silent success.** An absent or corrupt `build-result.json` is NEVER treated as `BUILD_COMPLETE` — this is Iron Law 8 (a gate that cannot evaluate its condition fails closed), and `build_result_reader.py` itself is written so it can never return `COMPLETE` for these inputs. Instead, inspect the worktree directly: `git -C "$WORKTREE" log <base>..HEAD` to determine whether the agent's commits landed despite the stalled/missing report. If commits are present, treat the phase as recoverable (resume from the last commit, or re-dispatch a continuation); if no commits are present, the build genuinely did not complete and the phase stays `in_progress` pending a fresh dispatch.
4. **FAILED -> recovery loop.** `status == "FAILED"` means the agent itself reported `BUILD_FAILED`; read `unresolved` and route into the standard CHANGES_REQUESTED / fix-engineer recovery loop (§ After CHANGES_REQUESTED) rather than branch-recovery.

**Spawn-prompt contract.** Every Build-phase spawn prompt MUST include the ABSOLUTE `state_dir` path (never a path the agent is expected to resolve relative to its own cwd — the orchestrator and the agent do not share a cwd). See `agents/software-engineer.md` § Write Result File and the equivalent section in the other 5 write-capable agent defs for the agent-side contract this satisfies.

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
Pipeline state lives in `$state_dir/[feature-name]/pipeline.md`. Each phase update records verdicts, artifacts, and agent summaries to this file. Legacy `$state_dir/[feature-name]-pipeline.md` files from before the DUAL_PATH migration remain readable during the soak window.

### Before Context Compression
When context is approaching limits:
1. Verify pipeline state is saved in `$state_dir/[feature-name]/pipeline.md`
2. Ensure it includes: current phase, all verdicts so far, outstanding findings, key file paths
3. The pipeline-state file IS the state — use `/harness:pipeline-resume` to recover on new session

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
[Review] RE-REVIEW 2/2 -- fixing: function body exceeds per-language limit in useNavigationHandler.ts
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

## 7c. Learning Extraction (automatic)

The auto-learn gate fires via the `auto-learn-gate.sh` Stop hook, not by orchestrator checklist. At the end of any turn where the gate thresholds are met (≥3 new pipeline observations, ≥3 pipelines or ≥24h since last `/harness:learn`, not already fired for the current pipeline), the hook prints a visible "Triggered: N observations, M pipelines" banner on stdout.

When the orchestrator sees that banner in context on its next turn, invoke `/harness:learn`. The `/harness:learn` skill itself resets the gate counters as its final step (see `skills/learn/SKILL.md` Step 10) — the hook is the *reminder*, `/harness:learn` is the actual extraction.

The orchestrator does not need to count observations, check dates, or evaluate conditions — the hook does all of that deterministically. Escape hatch for debugging or bulk-work sessions: set `CLAUDE_DISABLE_AUTO_LEARN=1`.

## Anti-Patterns (from real incidents)

### "I have a detailed plan, I'll just spawn agents directly"
**What happens:** The orchestrator has a plan with specific agent instructions, so it spawns frontend-engineer agents with detailed prompts, bypassing `/harness:build-implementation` or `/harness:refactor`. The code works, tests pass, but: no characterization tests were written (refactor safety), no RED-GREEN-REFACTOR audit trail (TDD), no structured verification, no formal gate closure.
**Fix:** Invoke the skill. The skill structures the work. The plan informs the skill, it does not replace it.

### "It's just a refactor, Verify/Test/Accept don't apply"
**What happens:** The orchestrator decides that a "pure structural refactor" doesn't need `/harness:verify` (no new boundaries to contract-test), `/harness:qa-test-strategy` (existing tests pass), or `/harness:product-acceptance` (no user-facing change). Three phases get skipped.
**Why it's wrong:** `/harness:verify` would catch that new extraction boundaries (hooks, helpers) have no dedicated tests -- mutation testing would reveal untested code. `/harness:qa-test-strategy` would flag coverage gaps. `/harness:product-acceptance` would verify the refactor didn't change behavior.
**Fix:** Every phase applies to every work type. The scope of each phase scales down for small tasks, but no phase is skipped.

### "CHANGES_REQUESTED, fixed it, moving on"
**What happens:** Reviewers return CHANGES_REQUESTED. The orchestrator spawns an engineer to fix, trusts the fix agent's self-report, and moves on without re-dispatching the reviewers. This means no independent verification that the fix is correct and the gate was never formally closed.
**Fix:** After fix, targeted re-review: re-dispatch only the reviewer(s) who raised findings. They check the addressed findings plus immediate surrounding context. Max 2 total rounds (initial + 1 re-review). Async when other work is available.
**Incident:** This happened on 2026-03-17 and is the reason the review protocol exists.

### "I'll spawn the reviewer agent directly -- same thing as the skill"
**What happens:** The orchestrator spawns a `code-reviewer` agent with a prompt describing what to review, bypassing `/harness:code-review`. The review happens but without the skill's structured checklist, severity framework, and verdict format.
**Why it's wrong:** Skills embed protocols. The `/harness:code-review` skill has a specific checklist (shape, DRY, SRP, test quality, error handling). Direct agent spawning lets the orchestrator define the review scope, which may omit checks.
**Fix:** Use Parallel Dispatch Protocol. Agents read and execute the skill file themselves. The prompt must include the skill file path (`~/.claude/skills/code-review/SKILL.md`), not a paraphrased version of the checklist.

### Continuity Anti-Patterns

- **Never start a new pipeline without checking for in-progress ones.** One pipeline at a time per branch.
- **Never discard pipeline state.** If the user wants to abandon, explicitly delete the memory file.
- **Never assume prior context.** Always read state from the memory file, not from "I remember from last time."

## Pre-flight Protocol (MANDATORY before any work begins)

1. **Check `pipeline-state/`** for in-progress pipelines before starting new work. If found, invoke `/harness:pipeline-resume`
1b. **Learn-status check** (see § Learn-Status Pre-flight Check below): consult `~/.claude/learning/{project-hash}/.learn-state.json` and either invoke a deferred `/harness:learn` or skip it for this pipeline.
2. **Classify the work**: feature, refactor, bug fix, or tech spike
3. **Map to entry skill**: `/harness:build-implementation`, `/harness:refactor`, `/harness:bug-fix`, or `/harness:tech-spike`
3b. **Check for scaffolding needs**: if the task requires new API endpoints, schema changes, infrastructure, or observability, flag the appropriate utility skill (see pipeline SKILL.md Step 2b)
4. **Enumerate all pipeline phases** and the skill for each
5. **Determine dispatch mode**: single-slice (subagents) or multi-slice/multi-domain (team)
6. **Create pipeline team**: `TeamCreate("pipeline-{task-id}")` -- always, even for single-slice (the team hosts review + final gate teammates)
6b. **Create pipeline scratchpad**: `mkdir -p $state_dir/{task-id}/scratchpad/` (see `protocols/autonomous-intelligence.md`)
6c. **Load session memory**: Read `session-memory/{project-hash}/` sub-files (`codebase-map.md`, `build-test.md`, `patterns.md`, `fragility.md` — `active-work.md` is orchestrator-only, never injected). Use `session_memory_read_split $hash $sub` so legacy single-file content is still tolerated during the 30-day DUAL_PATH soak. Seed from `session-memory/config/templates/{sub}.md` if first pipeline in this project.
7. **Write the phase plan** as a visible message to the user
8. **Execute phases in order**, spawning teammates for team phases, subagents for subagent phases. Inject session memory + scratchpad findings into every agent prompt (see `protocols/autonomous-intelligence.md` § Agent Spawn)

## Learn-Status Pre-flight Check

The learn-status check (Step 1b above) reads `~/.claude/learning/{project-hash}/.learn-state.json` and decides whether the prior pipeline's deferred `/harness:learn` invocation can run now or must defer one more pipeline.

Reflect § 6b spawns `/harness:learn` in the background (`run_in_background: true`) so the prior pipeline does not block on instinct extraction. The next pipeline's pre-flight is the queue point: if a `/harness:learn` run is still in flight, this pipeline's own Reflect § 6b invocation is **deferred** to the following pre-flight rather than overlapping.

### Signals (state file)

The signal lives in `~/.claude/learning/{project-hash}/.learn-state.json`:

- `last_learn_started` (ISO 8601 string, nullable) — stamped by `skills/learn/SKILL.md` Step 1 BEFORE any expensive work.
- `last_learn_run` (ISO 8601 string, nullable) — stamped by `skills/learn/SKILL.md` Step 10 on completion.

**Predicate**: a `/harness:learn` run is in flight ⇔ `last_learn_started > last_learn_run` OR `last_learn_run is null AND last_learn_started is not null`. Otherwise the system is idle.

The Python helper `hooks/_lib/learn_status.py` exposes `is_in_flight(state)` and `status_for_path(state_path)` returning `"in-flight" | "idle"` for any consumer that needs the predicate (orchestrator, hook, skill).

### Queue behaviour

At pre-flight Step 1b:

1. Resolve the project hash; read `.learn-state.json`.
2. Compute the predicate via `learn_status.is_in_flight(state)`.
3. If `"in-flight"`:
   - **Defer**: do NOT invoke `/harness:learn` for the previous pipeline at this pre-flight. The deferral is implicit in the predicate — `.learn-state.json` carries the only signal the queue needs, so no extra pipeline-state frontmatter field is written.
   - The next pre-flight (the pipeline AFTER this one) reads the same predicate; once `last_learn_run >= last_learn_started`, the deferred `/harness:learn` runs at that pre-flight as a background spawn.
4. If `"idle"`, decide by `last_fired_pipeline_id`:
   - **(a) Prior pipeline's banner fired but `/harness:learn` never started** (`last_fired_pipeline_id == prior_task_id` AND `last_learn_started <= last_learn_run`, i.e. the sentinel was never advanced): the prior spawn either never launched or crashed before Step 1b. Invoke `/harness:learn` now as a background spawn — same shape as Reflect § 6b.
   - **(b) Otherwise** (no recent banner, or the prior `/harness:learn` completed cleanly): no action at this pre-flight.

This converts Reflect § 6b ("invoke /harness:learn next turn") and pre-flight into a queue: at most one `/harness:learn` runs per project at a time, and overlapping firings are absorbed by deferral. The trade-off is at most one pipeline of latency before instincts are refreshed — acceptable because instincts are advisory, not gate-bearing.

## After CHANGES_REQUESTED (Review Loop Dispatch)

1. Spawn fix-engineer (`subagent_type: fix-engineer`, see `agents/fix-engineer.md`) into the same pipeline team with the specific findings. Pass the prior build's worktree path in the prompt — do NOT use `isolation: "worktree"` (that would create a fresh worktree without the build's commits). See `orchestrator/parallel-dispatch-details.md` § Review Phase Dispatch for the full spawn shape.
2. Fix-engineer fixes and commits on the same feature branch
3. Shut down fix-engineer, merge the fix branch
4. **Re-assign to the raising reviewer is MANDATORY.** The reviewer is still alive in the team with full context. Do not skip re-review because the fix "looks right."
5. `SendMessage` to the raising reviewer with: the original finding, the specific fix applied, and the file diff
6. **Targeted re-review**: Only the reviewer who raised the finding re-reviews
   - If code-reviewer raised findings and security-engineer APPROVED: only message code-reviewer
   - If both raised findings: message both, but each only re-reviews their own findings
7. The re-reviewer checks ONLY the addressed findings plus immediate surrounding context
8. Max 2 total rounds (initial + 1 re-review). If still not resolved, escalate to user
9. After both APPROVE: shut down both reviewers

### After UNVERIFIED with surviving mutants

**Gate predicate**: `verdict == UNVERIFIED AND surviving_mutants is non-empty`. Surviving mutants are the union of the verify report's `Tier 3 — Uncaught` list (rule-based mutation) and `Tier 3.5 — Uncaught` list (LLM-mutant pass). When verify returns UNVERIFIED but both `Uncaught:` lists are empty, this branch does NOT fire — the standard CHANGES_REQUESTED dispatch handles tier-failure-without-mutants.

When the gate fires, the orchestrator follows the same 9-step flow above (spawn fix-engineer with the prior worktree, fix, shut down, re-assign raising reviewer, max 2 rounds), with TWO additional verbatim sections inserted into the fix-engineer spawn prompt between `Findings to address` and `Build diff`. The role contract for fix-engineer (verify-finding-validity-first, no-scope-creep, no-compliance-commit-messages) lives in `agents/fix-engineer.md` and is unchanged on this branch.

**Surviving Mutants block**. Render one bullet per surviving mutant naming the field triple `file:line`, `category`, and `rationale`. Content is copied verbatim from the verify report's `Tier 3 — Uncaught` and `Tier 3.5 — Uncaught` sections — no field renaming, no schema invention. Tier 3 entries provide `file`, `line` (or `line_range`), and an operator description that maps to `category`. Tier 3.5 entries additionally carry `original`/`mutated` snippet pairs; render those as a parenthetical (e.g., `(mutated: <original> → <mutated>)`). Concatenate both lists; if only one tier produced surviving mutants, render only that tier's entries.

**Test-Authoring Directive block**. Direct fix-engineer to author one test per surviving mutant FIRST and see those tests RED on the unmutated code path BEFORE any production code change, then verify GREEN-after-fix kills the mutant. This inverts the gate from a score check to a test backlog: each mutant is a missing assertion, and the directive forces the fix-engineer to write the assertion before touching the implementation. Production-code edits made without a corresponding RED test are out-of-cycle scope creep and should be rejected at re-review.

**Design rationale**. This dispatch shape follows the Meta ACH (Assured LLM-Based Code-Health) work — see https://dl.acm.org/doi/10.1145/3696630.3728544 — which demonstrates that surfacing surviving mutants as concrete, addressable test gaps (rather than as a single aggregate score) materially improves the strength of the resulting test suite. The verify report already carries the per-mutant payload; this branch wires it into the existing fix-engineer dispatch without inventing new artifacts.

## Enforcement (Orchestrator Self-Discipline)

> **Iron law: NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED.** (Mirrored in `rules/core.md`.)

- If you catch yourself about to use Write or Edit on a source file, STOP
- If you catch yourself about to skip a skill invocation, STOP
- If you catch yourself about to spawn a write-capable subagent WITHOUT `isolation: "worktree"`, STOP (team teammates manage their own branches)
- If you catch yourself spawning an agent or teammate without referencing the skill file, STOP
- If you catch yourself keeping teammates alive across phases (idle token burn), STOP — shut them down
- The user saying "just fix it quickly" is not an excuse to bypass process
- The pipeline exists to catch mistakes. Every shortcut is a missed catch.

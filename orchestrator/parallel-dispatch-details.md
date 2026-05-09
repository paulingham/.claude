# Parallel Dispatch Details (Orchestrator-Only)

Extracted from `rules/_detail/parallel-dispatch-protocol.md`. Agents do not need this content.

## Team Creation

At pipeline start, create the team:

```
TeamCreate({
  team_name: "pipeline-{task-id}",
  description: "Pipeline for {feature name}"
})
```

One team per pipeline. All phase teammates join this team. The shared task list at `~/.claude/tasks/pipeline-{task-id}/` tracks all work.

## Team Dispatch

Every teammate spawn propagates `CLAUDE_SUBAGENT_DEPTH` through the spawn
shell so `hooks/depth-guard.sh` can refuse runaway recursion. Set
`CLAUDE_SUBAGENT_DEPTH = parent_depth + 1` in the shell that invokes the
Agent tool — the teammate inherits it via process env. See
`rules/_detail/agent-protocol.md > Resource Bounds` for caps and override semantics.

Example (orchestrator-side teammate spawn shell):

```bash
parent_depth="${CLAUDE_SUBAGENT_DEPTH:-0}"
child_depth=$((parent_depth + 1))
CLAUDE_SUBAGENT_DEPTH=$child_depth Agent \
  --subagent_type=code-reviewer \
  --team_name=pipeline-{task-id} \
  --name=reviewer-1 \
  --prompt="..."
```

The literal `CLAUDE_SUBAGENT_DEPTH=<N>` assignment must appear in the spawn
shell — not just in surrounding prose. The runtime-guard hook (`hooks/runtime-guard.sh`)
records the teammate's start time at this same call and emits a precise
`SendMessage({type:"shutdown_request", name:"<display>"})` directive on
stderr if the teammate later exceeds `CLAUDE_TEAMMATE_MAX_RUNTIME` (3600s
default). Subagent-class spawns (`team_name` empty) get a next-tool-call-blocked
directive — see `rules/_detail/parallel-dispatch-protocol.md > Resource Bounds`
for the Path-B disclosure.

## Plan Validation Phase Dispatch (Autonomous Mode)

Spawn both challengers in a single message:

```
// Step 1: Create tasks
TaskCreate({ title: "Plan review: product perspective", description: "Challenge scope, value, AC quality" })
TaskCreate({ title: "Plan review: engineering feasibility", description: "Challenge verticality, feasibility, error paths" })

// Step 2: Spawn challengers
Agent({
  name: "plan-reviewer",
  team_name: "pipeline-{task-id}",
  subagent_type: "product-reviewer",
  prompt: "You are reviewing a plan BEFORE implementation begins. This is NOT a code review --
    there is no code yet. You are validating the architect's design decisions.

    Read ~/.claude/agents/product-reviewer.md for your role definition.

    ## Your Task

    Challenge this plan. Your job is to catch bad plans before they become bad code.

    ## Challenge Checklist (verdict each: PASS / CONCERN / BLOCK)

    ### Scope
    - Is the scope right-sized for the stated complexity budget?
    - Are there features included that are not in the acceptance criteria (scope creep)?
    - Are there acceptance criteria NOT covered by any slice?

    ### Value
    - Does each slice deliver observable user value?
    - Is the ordering correct (highest value first)?

    ### AC Quality
    - Are all ACs in Given/When/Then format and testable?
    - Are error paths covered?

    ### Assumptions
    - What assumptions is this plan making? Which are validated vs. unvalidated?

    ### Alternatives
    - Were the alternatives genuinely different (not strawmen)?
    - Did the architect miss an obvious alternative?

    ## Output: Verdict (APPROVE / CHANGES_REQUESTED) + section analysis + specific recommended changes

    Plan under review:
    {architect_output}"
})

Agent({
  name: "plan-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "software-engineer",
  prompt: "You are reviewing a plan BEFORE implementation begins. This is NOT a code review --
    there is no code yet. You are validating feasibility from an implementation perspective.
    This is a plan review, not implementation. Do NOT create files or write code.

    Read ~/.claude/agents/software-engineer.md for your role definition.
    Read the project CLAUDE.md for tech stack and conventions.

    ## Your Task

    Challenge this plan from engineering feasibility. Catch plans that look good on paper
    but will fail in implementation.

    ## Challenge Checklist (verdict each: PASS / CONCERN / BLOCK)

    ### Vertical Slices
    - Is each slice truly end-to-end (input -> logic -> output -> test)?
    - Are there hidden horizontal slices? Can each be independently deployed?

    ### Technical Feasibility
    - Are the proposed patterns appropriate for this codebase?
    - Are estimated complexity budgets realistic per slice?

    ### Error Paths
    - Are all failure modes identified? Race conditions? Concurrency?

    ### Testability
    - Can each AC be tested at unit level? Are integration boundaries clear?

    ### Implementation Risk
    - What is the riskiest slice? Are there unknowns that should be a spike?
    - Is the parallel batch grouping correct (no shared file conflicts)?

    ### Better Approach
    - Would you approach this differently? Can complex slices be cut thinner?

    ## Output: Verdict (APPROVE / CHANGES_REQUESTED) + per-slice analysis + specific recommended changes

    Plan under review:
    {architect_output}"
})
```

On CHANGES_REQUESTED:
```
// 1. Re-spawn architect with combined feedback
Agent({
  subagent_type: "architect",
  prompt: "Read ~/.claude/agents/architect.md and ~/.claude/skills/epic-breakdown/SKILL.md.
    Your previous plan was challenged. Revise based on this feedback.

    Original plan: {plan}

    Challenger feedback:
    {combined_feedback}

    Requirements:
    - Address every BLOCK and CONCERN item
    - Include updated Alternatives Considered section
    - Do not make unrelated changes to approved aspects"
})

// 2. Re-submit to SAME challengers (still alive, have context)
// Only message the rejecting challenger(s) -- targeted re-review
SendMessage({
  to: "plan-reviewer",  // only if this challenger rejected
  message: "The architect has revised the plan based on your feedback.
    Revised plan: {revised_plan}
    Re-review ONLY the items you flagged. Do not re-review approved aspects."
})
```

After PLAN_APPROVED or PLAN_ESCALATED: shut down both challengers.

## Build Phase Dispatch

### Single Slice (subagent -- no team)

```
Agent({
  subagent_type: "frontend-engineer",
  isolation: "worktree",
  prompt: "Read ~/.claude/skills/build-implementation/SKILL.md and execute it fully.
    Read ~/.claude/agents/frontend-engineer.md for your role definition.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: Implement [feature], branch feature/X, base main.
    Acceptance criteria: [AC details]"
})
```

### Multi-Slice (team -- parallel engineers)

```
// Step 1: Create tasks
TaskCreate({ title: "Build: API endpoint for X", description: "ACs: ..." })
TaskCreate({ title: "Build: UI component for Y", description: "ACs: ..." })

// Step 2: Spawn teammates in single message, assign tasks
Agent({
  name: "backend-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "software-engineer",
  prompt: "Read ~/.claude/skills/build-implementation/SKILL.md and execute it fully.
    Read ~/.claude/agents/software-engineer.md for your role definition.
    Context: branch feature/X, base main.
    Your task: Build API endpoint for X. Check TaskList for details.
    Commit your work to a feature branch before completing."
})

Agent({
  name: "frontend-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "frontend-engineer",
  prompt: "Read ~/.claude/skills/build-implementation/SKILL.md and execute it fully.
    Read ~/.claude/agents/frontend-engineer.md for your role definition.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: branch feature/X, base main.
    Your task: Build UI component for Y. Check TaskList for details.
    Commit your work to a feature branch before completing."
})
```

After both complete: merge branches, shut down teammates.

### Planning Agent Dispatch (advisory, multi-slice Build only)

**Spawn condition**: `should_spawn_planning_agent(slice_count, dispatch_mode, phase)` returns True.
Evaluated at Build phase start, before build engineers are spawned.

**When spawned** (all must be true):
- `slice_count >= 2` (multi-slice Build)
- `dispatch_mode != "best-of-n"` (planning-agent is incoherent in Best-of-N races)
- `phase != "fix"` (fix-engineer scope is narrower than the plan)

**Spawn** (simultaneously with build engineers in a single message):
```python
Agent({
  subagent_type: "planning-agent",
  team_name: "pipeline-{task-id}",
  name: "planning-agent",
  model: "sonnet",
  prompt: """
TaskId: {task-id}
PlanPath: pipeline-state/{task-id}/plan.md
ScratchpadDir: pipeline-state/{task-id}/scratchpad/
TeamRoster: {comma-separated names of build engineer teammates}
PollSeconds: 60

Read ~/.claude/skills/continuous-planning/SKILL.md and execute it fully.
Read ~/.claude/agents/planning-agent.md for your role definition and edit-scope guard.
"""
})
```

**Single-slice path is UNCHANGED.** When `slice_count < 2`, the planning-agent is not spawned and all existing single-slice Build dispatch logic is unmodified.

**Shutdown**: Send `SendMessage({type: "shutdown_request", name: "planning-agent"})` AFTER sending shutdown to build engineers (let plan have its final cycle).

**Verdict** (emitted by planning-agent before exit):
- `PLAN_REFINED` — at least one Plan Update was appended
- `PLAN_UNCHANGED` — no contradictions found

Both verdicts are acceptable. The orchestrator logs the verdict in pipeline state but does not gate Build completion on it. Planning is advisory.

**Cost**: ~$0.05/build typical (Sonnet 4.6, ~20 poll cycles × ~700 tokens). Worst-case $0.60 at 200-turn budget exhaustion (planning silently stops, Build continues).

### Best-of-N Build Team Dispatch (conditional — `bestofn:true` from intake)

When `/intake` has tagged the task `bestofn: true` (computed in Step 2d-bis as `critical OR user_override`, where `user_override` fires on the literal `[best-of-n]` token in the request text), the Build phase dispatches as a Team variant that runs the same slice across N candidate models in parallel and picks the best output. This is NOT a separate skill — it is a dispatch mode of the Build Team. The winner still faces the normal Review → Final Gate → Ship gates; scoring selects *which* candidate faces those gates, it does not substitute for them.

The previous threshold (`task_class=="feature" AND Budget>=5`) was tightened to criticality-only after baseline data showed the 2-3x spend was not justified for non-critical features. Users who still want Best-of-N on a non-critical task pass `[best-of-n]` in their request.

**Procedure:**

0. **Pre-flight resource check (Wave-2 B11.2)**: source `skills/best-of-n/lib/score.sh` and call `check_worktree_capacity` against the project repo. Default cap is **6 worktrees on workstations, 12 on CI** (`CI=true`); override via `CLAUDE_BESTOFN_MAX_WORKTREES`. If the cap is exceeded → log `fallback-to-single-engineer` to the pipeline state's `## Re-routes` section and dispatch the standard single-engineer Build instead. This protects against disk/inode pressure on hosts that already have parallel sessions or abandoned pipelines holding worktrees open. Falling back is silent — the pipeline never halts and never asks the user.
1. **Load roster** from `skills/best-of-n/config.json`. Default: Opus 4.7 + Sonnet 4.6 (always included) + an optional external-frontier slot (GPT-5.3-Codex / Gemini 3.1 Pro) gated behind `required_env`. Respect `max_candidates` as an upper bound.
2. **Validate candidates**: drop any whose `required_env` is unset and emit `[best-of-n] Skipping {slug}: {required_env} not set`. For external candidates, call `skills/best-of-n/external-runner.sh`; if it exits non-zero, drop the candidate. Must end with ≥ 2 candidates or the dispatch aborts with `BEST_OF_N_FAILED` and the pipeline falls back to the standard single-engineer Build dispatch.
3. **Spawn one engineer teammate per candidate** into the pipeline team in a single message:
   ```
   Agent({
     subagent_type: "software-engineer",    // or "frontend-engineer" for UI slices
     isolation: "worktree",
     model: "<agent_model_param>",          // "opus" / "sonnet" / "haiku"
     team_name: "pipeline-{task-id}",
     name: "boN-{slug}",
     mode: "bypassPermissions",
     prompt: "<slice spec + ACs>
              Read ~/.claude/skills/build-implementation/SKILL.md and execute fully.
              Commit to branch: build/{task-id}-boN-{slug}"
   })
   ```
   External candidates are dispatched via `skills/best-of-n/external-runner.sh` (honest stub today; returns non-zero until a provider is wired). **Do not fabricate results** for external runners that fail.
4. **Collect results** per candidate: branch, commit SHA, test exit code, shape violation count (run `hooks/code-shape-check.sh` across changed files on the branch), diff size (`git diff --stat main..<branch>`).
5. **Spawn ONE code-reviewer teammate for selection** with the rubric:
   - `test_pass`: 1 if all tests green else 0 (dominant — broken code cannot win)
   - `shape_compliance`: `max(0, 1 - violations/10)`
   - `subjective_quality`: reviewer's 1-5 score on clarity + correctness, with written justification
   - `diff_size`: tie-breaker term — captured per-candidate in Step 4 via `git diff --stat main..<branch>` (records both `changed_files` and `changed_lines`). Spec for tie-break ordering: `(changed_files, changed_lines)` ascending — fewer files first, fewer lines second. Today `score.sh::pick_winner` collapses this to a single `diff_size` value (the lines column) and `skills/best-of-n/config.json::tie_breaker_order` encodes only `["diff_size_asc", "cost_asc"]`; the file-count split (in both the script and the config array) is a follow-up code change, tracked separately and out of scope for this slice.
   - Composite: `test_pass*1000 + shape_compliance*100 + subjective_quality*20 - (diff_size/100)`
   - **Tie-breaker order** (fires when `subjective_quality` AND `shape_compliance` are equal across the test-passing candidates — among test-passers, the integer-stepped 20× subjective term dominates the composite, so equal subjective+shape is the principled "near-tie" boundary):
     1. Fewer changed files; then
     2. Fewer changed lines; then
     3. Cheaper executor tier (sonnet < opus < external-frontier, integer ranks 1/2/3).
   - **Divergence record (advisory, no gate, no new verdict)**: when the top two candidates clear the tie-breaker boundary above AND their changed-files sets have Jaccard < 0.5 (non-overlapping work on the same slice), append a `category: decision` finding to `pipeline-state/{task-id}/scratchpad/best-of-n-selection.md` with winner/runner-up SHAs, per-candidate diff-stat, and the verbatim `## Selection Rationale`. The dispatch never writes `category: anti-pattern` — recurring divergence is mined into anti-pattern instincts only by `/learn` Step 3d via the standard observations.jsonl path (see `skills/learn/SKILL.md` § 3d), gated on `recurrence>=3 AND phases.review.rounds>=2`. `category: decision` is in the scratchpad enum at `rules/_detail/autonomous-intelligence.md` § Pipeline Scratchpad and is forwarded to reviewers and Final Gate roles by the existing injection matrix.
   - Reviewer MUST write a `## Selection Rationale` section — copied verbatim to the scratchpad for future `/learn` runs. The diff-stat and the Jaccard value (when the divergence record fires) are quoted in the rationale.
6. **Merge & cleanup**:
   - `git merge --no-ff build/{task-id}-boN-{winner-slug}` into the pipeline's working branch
   - For every loser: `git worktree remove --force <path>` then `git branch -D build/{task-id}-boN-{slug}`
   - Write `pipeline-state/{task-id}/best-of-n.md` (frontmatter: task_id, phase=build, verdict=BEST_OF_N_COMPLETE, timestamp; sections: Candidates Run, Winner, Selection Rationale, Cost Estimate Per Candidate)
   - Append `category: decision` note to `pipeline-state/{task-id}/scratchpad/best-of-n-selection.md`
7. **Winner proceeds to standard Review** — Best-of-N does not skip review or any subsequent gate.

**Fallback**: on `BEST_OF_N_FAILED` (insufficient candidates or all candidates failed their own tests), fall back to the standard single-engineer Build dispatch. Log the fallback in pipeline state under `## Re-routes`. Never halts.

**Helpers** (orchestrator-side, not skills):
- `skills/best-of-n/config.json` — roster, selection weights, tie-breaker order
- `skills/best-of-n/lib/score.sh` — sourceable pure-bash `score_candidate`, `pick_winner`, `check_budget_gate`
- `skills/best-of-n/external-runner.sh` — extension point for non-Anthropic candidates (honest stub today)
- `skills/best-of-n/tests/test_best_of_n.sh` — deterministic test of scoring, cleanup, and budget gate

## Review Phase Dispatch

Always uses the team. Spawn both reviewers in a single message:

```
// Step 1: Get the diff (orchestrator does this once)
git diff main...HEAD

// Step 2: Create tasks
TaskCreate({ title: "Code review: feature X", description: "Diff attached..." })
TaskCreate({ title: "Security review: feature X", description: "Diff attached..." })

// Step 3: Spawn reviewers
Agent({
  name: "code-reviewer",
  team_name: "pipeline-{task-id}",
  subagent_type: "code-reviewer",
  prompt: "Read ~/.claude/skills/code-review/SKILL.md and execute it fully.
    Read ~/.claude/agents/code-reviewer.md for your role definition.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: branch feature/X, base main.
    Changed files: [list]
    Full diff:
    [git diff output]
    Prior verdict: BUILD_COMPLETE

    Build agent decision record:
    [Decision Record from build state file — why choices were made]

    Build agent context for review:
    [Context for Review from build state file — uncertainty flags, areas needing focus]

    Agent memory (if exists):
    [Contents of agent-memory/code-reviewer/{project-hash}/memory.md]

    Learned patterns for this project (if any):
    [Top 5 instincts from learning/instincts/ filtered to role: code-reviewer]"
})

Agent({
  name: "security-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "security-engineer",
  prompt: "Read ~/.claude/skills/security-review/SKILL.md and execute it fully.
    Read ~/.claude/agents/security-engineer.md for your role definition.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: branch feature/X, base main.
    Changed files: [list]
    Full diff:
    [git diff output]
    Prior verdict: BUILD_COMPLETE

    Build agent decision record:
    [Decision Record from build state file — why choices were made]

    Agent memory (if exists):
    [Contents of agent-memory/security-engineer/{project-hash}/memory.md]

    Learned patterns for this project (if any):
    [Top 5 instincts from learning/instincts/ filtered to role: security-engineer]"
})
```

### Adversarial Review (Budget >= 10 OR Sensitive Code)

When the pipeline triggers adversarial review, spawn two code-reviewers with different focus prompts:

```
Agent({
  name: "reviewer-design",
  team_name: "pipeline-{task-id}",
  subagent_type: "code-reviewer",
  prompt: "Read ~/.claude/skills/code-review/SKILL.md and execute it fully.
    Read ~/.claude/agents/code-reviewer.md for your role definition.
    FOCUS: abstractions, naming clarity, DRY/SOLID, design quality, pattern appropriateness.
    DO NOT focus on edge cases or error paths (another reviewer handles that).
    Context: branch feature/X, base main.
    Changed files: [list]
    Full diff: [git diff output]"
})

Agent({
  name: "reviewer-edges",
  team_name: "pipeline-{task-id}",
  subagent_type: "code-reviewer",
  prompt: "Read ~/.claude/skills/code-review/SKILL.md and execute it fully.
    Read ~/.claude/agents/code-reviewer.md for your role definition.
    FOCUS: edge cases, error paths, integration concerns, race conditions, concurrency issues.
    DO NOT focus on naming or design patterns (another reviewer handles that).
    Context: branch feature/X, base main.
    Changed files: [list]
    Full diff: [git diff output]"
})
```

After both return:
- Findings flagged by both → HIGH confidence
- Findings flagged by only one → MEDIUM confidence (include both perspectives)
- Both APPROVE → advance. Either CHANGES_REQUESTED → normal review loop with the raising reviewer.

### Review Loop with Teams

On CHANGES_REQUESTED:

```
// 1. Spawn fix-engineer into the same team
//    NOTE: fix-engineer is its own agent (agents/fix-engineer.md) — it
//    operates on the prior build's worktree (NOT a fresh worktree) and
//    has fix-cycle-specific guidance (verify finding validity first,
//    no scope creep, no compliance commit messages, no source-code
//    apology comments).
Agent({
  name: "fix-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "fix-engineer",
  // Pass the prior build's worktree path so the fix targets the same
  // branch the build engineer produced. The path comes in via the
  // prompt's `Working directory:` line (see agents/fix-engineer.md
  // § Where You Run). Do NOT pass `isolation: "worktree"` here — that
  // creates a fresh worktree off main without the build's commits, so
  // the fix lands on the wrong tree and `git diff main...HEAD` shows
  // nothing for the fix-engineer to address. This is a known pitfall
  // — reproduced in the wave5-hygiene rev1 fix cycle (May 2026).
  prompt: "Read ~/.claude/agents/fix-engineer.md for your role definition.
    Working directory: <prior-build-worktree-path>
    Branch: <feature-branch-the-build-was-on>
    Round: 1 (or 2 on re-review)
    Findings to address: [verbatim reviewer text + cited file:line]
    Build diff: [git diff main...HEAD]
    Verify each finding is valid before implementing.
    If a suggestion would make code worse, return verdict
    FIX_REJECTED_TECHNICAL with justification.
    Commit with descriptive message (not 'fixed per review feedback')."
})

// 2. After fix-engineer completes, shut it down
SendMessage({ to: "fix-engineer", message: { type: "shutdown_request" } })

// 3. Merge fix branch, then re-assign to raising reviewer (STILL ALIVE)
SendMessage({
  to: "code-reviewer",
  message: "Re-review: Finding F1 (method body > 8 lines) was addressed.
    Fix diff: [diff]. Check the fix addresses the finding.
    Re-review ONLY the addressed findings, not the full codebase."
})
```

The reviewer **already has context** from the first review. No prompt reconstruction needed.

**Fix agent review-receiving rules** (include in fix agent prompt):
- Verify the reviewer's finding before implementing -- read the cited code, confirm the concern applies
- If the suggestion would make code worse, report back with technical justification instead of blindly complying
- Commit messages describe WHAT changed and WHY -- never "fixed per review feedback"

Maximum 2 total rounds (initial + 1 re-review). If not resolved, escalate to user.

After both APPROVE: shut down both reviewers.

## Final Gate Phase Dispatch

Three phases that currently run sequentially now run in parallel:

```
// Step 1: Create tasks
TaskCreate({ title: "Verify: contract + smoke + mutation", description: "..." })
TaskCreate({ title: "Test: coverage analysis + gap filling", description: "..." })
TaskCreate({ title: "Accept: AC validation + UX review", description: "..." })

// Step 2: Spawn all three in single message
Agent({
  name: "verifier",
  team_name: "pipeline-{task-id}",
  subagent_type: "qa-engineer",
  prompt: "Read ~/.claude/skills/verify/SKILL.md and execute it fully.
    Read ~/.claude/agents/qa-engineer.md for your role definition.
    Context: branch feature/X, all tests passing, review APPROVED.
    Run contract tests, smoke tests, and mutation testing on changed files."
})

Agent({
  name: "test-analyst",
  team_name: "pipeline-{task-id}",
  subagent_type: "qa-engineer",
  prompt: "Read ~/.claude/skills/qa-test-strategy/SKILL.md and execute it fully.
    Read ~/.claude/agents/qa-engineer.md for your role definition.
    Context: branch feature/X, ACs: [list].
    Map ACs to tests, identify coverage gaps, write missing tests."
})

Agent({
  name: "product-reviewer",
  team_name: "pipeline-{task-id}",
  subagent_type: "product-reviewer",
  prompt: "Read ~/.claude/skills/product-acceptance/SKILL.md and execute it fully.
    Read ~/.claude/agents/product-reviewer.md for your role definition.
    Context: branch feature/X, ACs: [list].
    Validate all ACs are met, assess UX quality, verify business value."
})
```

After all three return verdicts: shut down teammates.

## Multi-Persona Patch Critic Dispatch (critical OR Budget >= 7)

The patch-critic role in the Final Gate Team has two dispatch modes selected by criticality + budget. The other three Final Gate roles (verify + test + accept) are unchanged.

| Mode | Gate condition | Spawn shape |
|---|---|---|
| single-critic (default) | `!critical AND Budget < 7` | one `patch-critic` Agent call alongside verifier/test-analyst/product-reviewer |
| multi-persona variant | `critical == true OR Budget >= 7` | three parallel `patch-critic` Agent calls, one per persona, alongside verifier/test-analyst/product-reviewer |

Background: inspired by Multi-Agent Reflexion (Yu et al., arXiv 2512.20845) where multiple persona-critics escape single-agent confirmation bias. Cost is ~3x patch-critic spend; the gate already runs in parallel with verify+test+accept and is a rounding error vs build/review spend on critical work.

**Composition with C8 anti-pattern mining (#80)**: complementary, not redundant. Multi-persona catches in-cycle (during this gate); C8 mines cross-pipeline patterns from observation rounds-counts after pipelines close. The schema extension in `rules/_detail/autonomous-intelligence.md` § Observation Capture (`phases.patch_critic.rounds`) wires the variant's rejections into C8's mining gate so consistently-caught-but-not-by-code-review patterns become anti-pattern instincts over time. They cover different time horizons.

**Procedure (variant mode):**

1. **Gate check**: read pipeline state. If `critical != true AND Budget < 7`, dispatch single-critic and skip the rest of this procedure.

2. **Spawn three personas in a single message** (parallel — no persona sees another persona's output):

   ```
   Agent({
     name: "patch-critic-correctness",
     team_name: "pipeline-{task-id}",
     subagent_type: "patch-critic",
     prompt: "Read ~/.claude/agents/patch-critic.md for your role definition.

       Persona: correctness
       Weight § 1 (Tests cover the change) and § 5 (Accessibility) heaviest.
       Search emphasis: 'Did the diff actually solve the spec? Are tests load-bearing
       for the behavior change?'

       You score every rubric dimension regardless of specialty. You do NOT see the
       other personas' outputs. Independent context is the design.

       Context: branch feature/X, base main.
       Candidate diff: [git diff main...HEAD]
       Test output: [most recent fresh test-suite run]
       Intake spec: [task description]
       A11y index (if present): pipeline-state/{task-id}/design-qc/index.json"
   })

   Agent({
     name: "patch-critic-regression-risk",
     team_name: "pipeline-{task-id}",
     subagent_type: "patch-critic",
     prompt: "Read ~/.claude/agents/patch-critic.md for your role definition.

       Persona: regression-risk
       Weight § 3 (No obvious regressions visible from diff) heaviest.
       Search emphasis: 'What worked before this diff that could break now?
       Removed null guards, weakened validation, broadened catches that swallow
       errors, lost edge-case branches, removed tests, changed defaults that
       callers rely on.'

       You score every rubric dimension regardless of specialty. You do NOT see the
       other personas' outputs. Independent context is the design.

       Context: branch feature/X, base main.
       Candidate diff: [git diff main...HEAD]
       Test output: [most recent fresh test-suite run]
       Intake spec: [task description]"
   })

   Agent({
     name: "patch-critic-scope-creep",
     team_name: "pipeline-{task-id}",
     subagent_type: "patch-critic",
     prompt: "Read ~/.claude/agents/patch-critic.md for your role definition.

       Persona: scope-creep
       Weight § 2 (Diff minimal vs spec) and § 4 (No incidental refactor) heaviest.
       Search emphasis: 'What is in this diff that the spec did NOT ask for?
       Renames, moves, reorgs, drive-by cleanups, opportunistic typing tweaks.'

       You score every rubric dimension regardless of specialty. You do NOT see the
       other personas' outputs. Independent context is the design.

       Context: branch feature/X, base main.
       Candidate diff: [git diff main...HEAD]
       Test output: [most recent fresh test-suite run]
       Intake spec: [task description]"
   })
   ```

3. **Aggregation rule (OR)**:
   - All three personas return `PATCH_APPROVED` → gate verdict `PATCH_APPROVED`.
   - Any persona returns `PATCH_REJECTED` (any MEDIUM+ severity finding on any dimension) → gate verdict `PATCH_REJECTED`. Forward findings from ALL rejecting personas to fix-engineer.
   - The orchestrator MUST NOT silently override a single-persona MEDIUM+ rejection because the other two passed. OR-aggregation is the design, not a soft hint.

4. **Audit artifact**: write `pipeline-state/{task-id}/patch-critic.md` with frontmatter (`task_id, phase=final-gate, verdict, timestamp, mode=multi-persona`) and three sections (one per persona). Include each persona's full Rubric table + Findings list verbatim. The orchestrator-aggregated verdict appears in frontmatter and at the top of the file.

5. **Divergence record on split votes** (one persona REJECTs, others PASS — i.e., not unanimous): append a `category: decision` finding to `pipeline-state/{task-id}/scratchpad/patch-critic-divergence.md`. Pattern matches Best-of-N's divergence record. Body includes: rejecting persona, dimension, severity, finding text, file:line. `/learn` mines split-vote dimensions over time; consistently-split dimensions are calibration targets (rubric clarity issue, not a persona problem).

6. **PATCH_REJECTED → fix → re-critique ALL personas** (NOT just the rejecting persona). Differs from existing Review pattern (re-dispatch only the rejecting reviewer). The fix may have introduced a new issue in another persona's territory. Cost is acceptable on critical/Budget>=7 work. Maximum 2 total rounds (initial + 1 re-critique), matching the existing Review cap. After 2 rounds with persistent rejection → escalate to user. Should be rare under the In-Cycle Fix Rule.

7. **Partial completion contract**: if a persona fails to return within timeout (`CLAUDE_SUBAGENT_MAX_RUNTIME`, default 1800s), treat as `PATCH_REJECTED` with reason `persona-timeout`. Re-dispatch only the missing persona (1 retry). After 2 timeouts on the same persona → escalate per retry-twice-then-escalate. Do NOT silently skip a timed-out persona — a missing verdict is not an approval.

8. **Observation capture** (Reflect step): record per-persona verdicts and rejecting findings in `phases.patch_critic` per `rules/_detail/autonomous-intelligence.md` § Observation Capture. The `rounds` count and `persona_rejections` array feed C8 anti-pattern mining on subsequent pipelines.

**Why no debate round (vs the paper)**: patch-critique is closed-form (fixed rubric, fixed dimensions, binary-per-finding-after-severity). The paper's debate coordinator targets open-ended reflexion (HotPotQA answers, HumanEval code generation). Three independent strict scorers + OR-aggregation captures the "different priors → different blind spots" lift without the 2x debate-round overhead.

### Execution Evidence (optional, default off)

OPTIONAL enrichment that prepends a short `## Execution Evidence` block to every persona spawn prompt before dispatch. Inspired by Agentic Verifier (arXiv 2602.04254), where giving the verifier execution traces of the candidate against discriminative inputs catches a class of regression that diff-only review misses. The path is purely additive — when the flag is unset OR any of three downstream steps silently skip, the dispatch falls through to the existing #93 procedure exactly (`1. Gate check` → `2. Spawn three personas` → `3. Aggregation rule (OR)` → … unchanged).

**Step 0 — Env-var probe**:

- Read `CLAUDE_PATCH_CRITIC_EXEC_LAYER` from the orchestrator-side env. Defaults unset / off. Only the literal value `1` enables the path; any other value (including empty, `0`, `true`, `yes`) coerces to off — the same conservative pattern used by other harness opt-in flags.
- When unset / off → SKIP the entire sub-section. Dispatch personas exactly as #93 specifies (Step 1 onward in this section). This is the default and the path THIS pipeline's own Final Gate runs against; the env var is operator-set, never harness-set (enforced as a committed invariant by the AC3.7 grep guard shipping in Slice 3).

**Once-per-slice contract**: when the flag is on AND the path proceeds, the orchestrator generates discriminative test inputs ONCE per slice, runs them ONCE, formats the result into a single `## Execution Evidence` block, and APPENDS the SAME block VERBATIM to each of the three persona spawn prompts. Evidence is shared across personas because (a) inputs are derived from the diff and the diff is identical across personas, so per-persona inputs would be identical too, and (b) persona differentiation already lives in the existing search-emphasis prompts (rubric-dimension weighting), not in raw evidence. The once-per-slice scope is both 3x cheaper and signal-equivalent — per-persona generation would produce identical inputs (the diff is identical), wasting the spend.

**Three silent skip points** — any one collapses to identical diff-only dispatch (no error surfaced, no log noise, persona spawns unchanged):

1. Flag off (Step 0 above) — env var unset or any value other than `1`.
2. Generator failure — the discriminative-test-input LLM call times out, returns malformed JSON, or returns zero non-equivalent inputs (Slice 2).
3. Run / execution failure — sandbox unavailable, no inferable entry point, or all inputs time out during the apply-test-revert loop (Slice 3).

Each skip point falls through to the existing dispatch exactly as #93 specifies; the personas never observe the difference, the rubric is unchanged, the verdict semantics are unchanged.

**Re-critique semantics**: when patch-critic returns `PATCH_REJECTED` and fix-engineer produces an updated diff, the orchestrator regenerates the execution-evidence block from scratch on each re-dispatch — the diff has changed, so the discriminative inputs and run output may differ. There is NO caching across rounds; per-dispatch regeneration is the contract.

**Forensic record**: the observation-schema `phases.patch_critic.evidence_mode` field (see `rules/_detail/autonomous-intelligence.md` § Field reference) records `"diff-only"` when any skip point fires (or when the flag is unset) and `"diff+execution"` only when all three steps complete successfully. Readers MUST tolerate absence of the field as a legacy / pre-exec-layer record.

Slices 2 and 3 fill in Steps 1-3 (input generation, sandboxed run, prompt-append point). This sub-section establishes Step 0 (the gate) and the silent-fallback semantics — when Slices 2-3 land, they extend this sub-section but do NOT alter the gate or the fallback contract.

**Hedges (PROVISIONAL until baseline run)**:

- Variant gated on `critical OR Budget >= 7`. Single-critic remains the default for routine work — DO NOT enable for `!critical AND Budget < 7`.
- OR-aggregation is intentionally conservative (biased toward false positives). Fix-engineer absorbs the rework cost; a missed regression at Final Gate costs more than an extra fix-engineer round.
- Disagreement rate is the kill-switch metric. If `/forensics` reports < 5% persona disagreement over a 30-pipeline window, drop back to single critic — the variant is no longer earning its 3x spend. If disagreement is > 30%, the personas are catching distinct things — variant justified. The 5–30% band is the working range.
- Empirical baseline is REQUIRED before promoting from PROVISIONAL. Baseline establishes false-positive rate vs single-critic on the harness regression suite (`/internal-eval`). The paper's HumanEval lift (76% → 82% Pass@1) does NOT directly translate to patch-critique acceptance/rejection — different domain, different decision shape.

## Teammate Shutdown

After each team phase completes:

```
SendMessage({ to: "teammate-name", message: { type: "shutdown_request" } })
```

After pipeline completes, clean up:
- Shut down any remaining teammates
- Team files at `~/.claude/teams/pipeline-{task-id}/` are auto-cleaned
- Task list at `~/.claude/tasks/pipeline-{task-id}/` is auto-cleaned

## Inter-Agent Communication (hcom)

When hcom is installed and hooks are registered:

### File Collision Detection
During multi-slice Build with parallel worktrees, hcom watches for file edits across agents. If two agents modify the same file within 30 seconds, hcom emits a collision warning via stderr. This prevents merge conflicts from being discovered at merge time — catching them while agents are still working.

### Direct Messaging During Team Phases
Teammates can message each other via hcom without routing through the orchestrator:
- Useful for: reviewer asking build-engineer a question, engineer notifying reviewer of a fix
- Messages arrive mid-turn or wake idle agents

### Activation
hcom hooks should only be active during team phases (check `CLAUDE_PIPELINE_TASK_ID` is set). Disable for solo subagent phases to avoid noise. The hcom hooks are gated by the presence of the pipeline task ID env var.

### Transcript Sharing
hcom enables transcript sharing for context handoffs — e.g., the architect's design reasoning is available to the software-engineer without the orchestrator reconstructing it in a prompt.

## Waiting for Checkpoints

Use `scripts/await-pattern.sh` instead of sleep-poll loops when waiting for a background process or teammate to reach a known-ready state.

**Usage:**

```bash
# Start background process, redirect stdout to a log file
nohup some-command >"$log" 2>&1 &
BG_PID=$!

# Block until checkpoint marker appears or timeout fires
scripts/await-pattern.sh "$log" '\[CHECKPOINT\] tests-green' 600 50000
case $? in
  0)   echo "Checkpoint reached" ;;
  124) echo "Timed out after 600s"; kill "$BG_PID" ;;
  1)   echo "Error (bad args, missing log, or max_lines exceeded)" ;;
esac
```

**Exit codes:** 0=matched, 124=timeout (matches GNU `timeout` convention), 1=bad-args/missing-file/max_lines-exceeded

**Logging:** every call appends one JSONL record to `metrics/${CLAUDE_SESSION_ID}/await-events.jsonl` with `record_type: await_match | await_timeout`.

**Checkpoint vocabulary:** See `rules/_detail/parallel-dispatch-protocol.md § Checkpoint Vocabulary` for standard marker strings.

### Deprecation: Sleep-Poll Loops

Sleep-poll loops are deprecated in orchestrator code:

```bash
# DEPRECATED — do not write new code like this
while ! grep -q '\[CHECKPOINT\] tests-green' "$log"; do
  sleep 2
done
```

Problems with sleep-poll: wastes CPU on idle wakeups, racy against line-buffered output, no structured audit trail, no timeout enforcement, no max_lines protection.

Use `await-pattern.sh` instead.

## Audit Trail

For each team phase, the orchestrator records:

```
[Build] TEAM PHASE -- 2 engineers spawned (backend-engineer, frontend-engineer)
[Build] COMPLETE -- both tasks done, branches merged
[Review] TEAM PHASE -- code-reviewer + security-engineer spawned
[Review] VERDICTS -- code-reviewer: APPROVE, security-engineer: CHANGES_REQUESTED (1 HIGH)
[Review] FIX -- fix-engineer spawned, fixing: [finding]. Shut down after fix.
[Review] RE-REVIEW -- re-assigned to security-engineer (context preserved)
[Review] VERDICT -- security-engineer: APPROVE
[Review] COMPLETE -- both APPROVE, reviewers shut down
[Final Gate] TEAM PHASE -- verifier + test-analyst + product-reviewer spawned
[Final Gate] VERDICTS -- VERIFIED + COVERED + APPROVED
[Final Gate] COMPLETE -- all shut down
```

## Batch Execution (Pre-Planned Work)

When executing multiple pre-planned tasks in parallel (e.g., production readiness waves), use `/batch-pipeline` instead of driving phases manually. The batch pipeline preserves critical infrastructure while skipping redundant phases.

### Why batch-pipeline exists

The full `/pipeline` (Plan → Plan Validation → Build → Review → Final Gate → Ship → Deploy → Reflect) is designed for new work that needs classification and planning. Pre-planned batch work (where the architect output already exists as a document) can skip Plan and Plan Validation, but **must not skip** state tracking, scratchpad, session memory, or the learning loop.

### What the orchestrator must NOT do for batch work

- Spawn build agents directly without creating pipeline state first
- Skip review (code-review + security-review are always mandatory)
- Skip the Reflect step (observations, session memory, cleanup)
- Drive phases manually without state file tracking
- Forget to inject session memory, scratchpad, and instincts into agent prompts

### What changes vs single-task pipeline

| Aspect | Single task | Batch |
|--------|-------------|-------|
| Entry point | `/intake` → `/pipeline` | `/batch-pipeline` |
| Plan phase | Architect designs | Already done (plan document) |
| Plan validation | User or challengers approve | Already approved |
| Build dispatch | 1 agent or team | N agents in parallel |
| Review dispatch | Team (persistent reviewers) | Subagents (parallel, per-task) |
| Final Gate | verify + test + accept team | Skipped (batch items are typically small) |
| State tracking | Same | Same (one state file per batch) |
| Scratchpad | Same | Shared across all batch agents |
| Observations | Same | One observation per batch |

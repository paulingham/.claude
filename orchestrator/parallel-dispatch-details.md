# Parallel Dispatch Details (Orchestrator-Only)

Extracted from `rules/parallel-dispatch-protocol.md`. Agents do not need this content.

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
`rules/agent-protocol.md > Resource Bounds` for caps and override semantics.

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
directive — see `rules/parallel-dispatch-protocol.md > Resource Bounds`
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
PlanPath: pipeline-state/{task-id}-plan.md
ScratchpadDir: pipeline-state/{task-id}-scratchpad/
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
// 1. Spawn fix engineer into the same team
Agent({
  name: "fix-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "software-engineer",
  prompt: "Read ~/.claude/agents/software-engineer.md for your role definition.
    Fix these review findings: [findings]
    Verify each finding is valid before implementing.
    If a suggestion would make code worse, report back with justification.
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

**Checkpoint vocabulary:** See `rules/parallel-dispatch-protocol.md § Checkpoint Vocabulary` for standard marker strings.

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

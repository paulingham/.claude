# Parallel Dispatch Details (Orchestrator-Only)

Extracted from `rules/parallel-dispatch-protocol.md`. Agents do not need this content.

## Dispatch Procedure

### Step 1: Spawn Agents in a Single Message

The orchestrator spawns all parallel agents in one message. Each agent prompt includes the skill file path. The orchestrator does NOT read the skill files itself -- agents read them independently.

### Step 2: Agents Read and Execute Their Skill Files

Each agent reads its assigned skill file at `~/.claude/skills/[name]/SKILL.md` and follows its procedure, checklist, and output format. The agent also reads the project's tech stack pattern file if one exists at `~/.claude/skills/[stack]-patterns/SKILL.md`.

### Step 3: Orchestrator Collects Verdicts

After all agents complete, the orchestrator reads each agent's output, extracts the verdict, and determines the next phase based on the combined results.

## Review Phase Example

Dispatch both reviewers in a single message:

```
// Single message, two Agent calls -- true parallel execution
Agent({
  subagent_type: "code-reviewer",
  prompt: "Read the skill file at ~/.claude/skills/code-review/SKILL.md and execute it fully.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: branch feature/X, base main, changed files: [list], prior verdict: BUILD_COMPLETE"
})

Agent({
  subagent_type: "security-engineer",
  prompt: "Read the skill file at ~/.claude/skills/security-review/SKILL.md and execute it fully.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: branch feature/X, base main, changed files: [list], prior verdict: BUILD_COMPLETE"
})
```

## Build Phase Example

Parallel worktrees for independent slices, each loading the tech stack pattern:

```
// Independent slices -- parallel worktrees in single message
Agent({
  subagent_type: "frontend-engineer",
  isolation: "worktree",
  prompt: "Read the skill file at ~/.claude/skills/build-implementation/SKILL.md and execute it fully.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: Implement [AC 1], branch feature/X, base main.
    Acceptance criteria: [AC 1 details]"
})

Agent({
  subagent_type: "software-engineer",
  isolation: "worktree",
  prompt: "Read the skill file at ~/.claude/skills/build-implementation/SKILL.md and execute it fully.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: Implement [AC 2], branch feature/X, base main.
    Acceptance criteria: [AC 2 details]"
})
```

## Review Loop Integration

The review follows targeted re-review, not full re-dispatch:

```
Parallel Dispatch (code-reviewer + security-engineer)
  -> Both APPROVE? -> proceed to Verify
  -> CHANGES_REQUESTED? -> spawn engineer to fix -> targeted re-review by raising reviewer(s) only
```

Maximum 2 total rounds (initial + 1 re-review). If not resolved, escalate to user:

```
[ESCALATION] Review not resolved after 2 rounds

Context: [findings still unresolved after targeted re-review]
Options:
1. Continue with known findings documented
2. Reassign to different engineer
3. Descope the change

Recommendation: [based on finding severity]
```

When other work is available, spawn review agents async (`run_in_background: true`) and continue with the user on other tasks.

## Audit Trail

For each parallel dispatch, the orchestrator records:

```
[Review] PARALLEL DISPATCH -- code-reviewer + security-engineer spawned
[Review] VERDICTS -- code-reviewer: APPROVE, security-engineer: CHANGES_REQUESTED (1 HIGH)
[Review] RE-REVIEW 2/2 -- fixing: [finding description]. Re-dispatching security-engineer...
[Review] VERDICT -- security-engineer: APPROVE
[Review] COMPLETE -- both APPROVE after targeted re-review
```

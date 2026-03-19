# Parallel Dispatch Protocol

## Purpose

The Skill tool loads skill content inline into the orchestrator's context and executes sequentially. The Agent tool spawns independent agents that run in parallel when multiple calls are made in a single message. For phases that MUST run in parallel (Review, independent Build slices, Verify Tier 1+2), agents read and execute their own skill files instead of the orchestrator invoking skills via the Skill tool.

This protocol enables TRUE parallel execution while preserving skill structure and audit trails.

## Parallel Phase Map

| Phase | Skills | Agent Types | Dispatch |
|-------|--------|-------------|----------|
| Review | `/code-review` + `/security-review` | code-reviewer + security-engineer | Single message, two Agent calls |
| Build (independent slices) | `/build-implementation` x N | software-engineer / frontend-engineer | Single message, N worktree Agent calls |
| Verify Tier 1+2 | `/verify` (Tier 1 + Tier 2) | qa-engineer or software-engineer | Single message, two Agent calls where tiers are independent |

## Dispatch Procedure

### Step 1: Spawn Agents in a Single Message

The orchestrator spawns all parallel agents in one message. Each agent prompt includes the skill file path. The orchestrator does NOT read the skill files itself -- agents read them independently.

### Step 2: Agents Read and Execute Their Skill Files

Each agent reads its assigned skill file at `~/.claude/skills/[name]/SKILL.md` and follows its procedure, checklist, and output format. The agent also reads the project's tech stack pattern file if one exists at `~/.claude/skills/[stack]-patterns/SKILL.md`.

### Step 3: Orchestrator Collects Verdicts

After all agents complete, the orchestrator reads each agent's output, extracts the verdict, and determines the next phase based on the combined results.

## Agent Prompt Template

```
Read the skill file at ~/.claude/skills/[name]/SKILL.md and execute it fully.
Also read ~/.claude/skills/[stack]-patterns/SKILL.md for tech-specific guidance if it exists.

Context:
- Branch: [branch name]
- Base branch: [main/master]
- Changed files: [list or git diff --stat output]
- Prior verdict: [previous phase verdict]
- Tech stack: [from project CLAUDE.md]
```

## Review Phase Example

Dispatch both reviewers in a single message:

```
// Single message, two Agent calls — true parallel execution
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
// Independent slices — parallel worktrees in single message
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

## What This Protocol Is NOT

- **NOT permission to skip skills.** Agents must read and execute the full skill file. The skill's checklist, procedure, and output format are mandatory.
- **NOT for sequential phases.** Build (single slice), Verify (Tier 3 after Tier 1+2), Test, Accept, and Ship remain sequential via the Skill tool.
- **NOT a shortcut.** The protocol adds structure (skill file loading) to parallel dispatch. Spawning agents without skill file references is still an anti-pattern.

## Why Agents Read the Skill File

- **Context efficiency**: Only the executing agent loads the skill content, not the orchestrator. Reduces orchestrator context usage.
- **No paraphrase risk**: The agent reads the original skill file, not a summarized version. No information is lost in translation.
- **Single source of truth**: The skill file remains the authoritative protocol. Updates to the skill file automatically apply to all future dispatches.
- **Separation of concerns**: The orchestrator decides WHEN and WHAT to dispatch. The agent decides HOW by reading the skill.

## Review Loop Integration

The review loop follows the same dispatch pattern:

```
Parallel Dispatch (code-reviewer + security-engineer)
  -> Both APPROVE? -> proceed to Verify
  -> CHANGES_REQUESTED? -> spawn engineer to fix -> re-dispatch BOTH reviewers -> repeat
```

Maximum 3 review loop iterations. If both reviewers have not returned APPROVE after 3 rounds, escalate to user:

```
[ESCALATION] Review loop exceeded 3 iterations

Context: [findings still unresolved after 3 fix attempts]
Options:
1. Continue with known findings documented
2. Reassign to different engineer
3. Descope the change

Recommendation: [based on finding severity]
```

## Audit Trail

For each parallel dispatch, the orchestrator records:

```
[Review] PARALLEL DISPATCH — code-reviewer + security-engineer spawned
[Review] VERDICTS — code-reviewer: APPROVE, security-engineer: CHANGES_REQUESTED (1 HIGH)
[Review] LOOP 2/3 — fixing: [finding description]. Re-dispatching...
[Review] VERDICTS — code-reviewer: APPROVE, security-engineer: APPROVE
[Review] COMPLETE — both APPROVE on round 2
```

# Parallel Dispatch Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/parallel-dispatch-details.md`

## Purpose

For phases that MUST run in parallel (Review, independent Build slices, Verify Tier 1+2), agents read and execute their own skill files instead of the orchestrator invoking skills via the Skill tool. This enables true parallel execution while preserving skill structure and audit trails.

## Parallel Phase Map

| Phase | Skills | Agent Types | Dispatch |
|-------|--------|-------------|----------|
| Review | `/code-review` + `/security-review` | code-reviewer + security-engineer | Single message, two Agent calls |
| Build (independent slices) | `/build-implementation` x N | software-engineer / frontend-engineer | Single message, N worktree Agent calls |
| Verify Tier 1+2 | `/verify` (Tier 1 + Tier 2) | qa-engineer or software-engineer | Single message, two Agent calls where tiers are independent |

## Agent Prompt Template

The orchestrator MUST pre-compute the diff and include changed file contents in the reviewer prompt. This saves reviewers 5-10 turns of file reading.

```
Read the skill file at ~/.claude/skills/[name]/SKILL.md and execute it fully.
Also read ~/.claude/skills/[stack]-patterns/SKILL.md for tech-specific guidance if it exists.

Context:
- Branch: [branch name]
- Base branch: [main/master]
- Changed files: [list]
- Full diff: [orchestrator pre-computes and includes git diff output here]
- Changed file contents: [orchestrator pre-reads and includes full content of each changed file]
- Prior verdict: [previous phase verdict]
- Tech stack: [from project CLAUDE.md]
```

## What This Protocol Is NOT

- **NOT permission to skip skills.** Agents must read and execute the full skill file.
- **NOT for sequential phases.** Build (single slice), Verify (Tier 3), Test, Accept, Ship remain sequential.
- **NOT a shortcut.** Spawning agents without skill file references is still an anti-pattern.

## Why Agents Read the Skill File

- **Context efficiency**: Only the executing agent loads the skill content, not the orchestrator.
- **No paraphrase risk**: The agent reads the original skill file, not a summary.
- **Single source of truth**: The skill file is authoritative. Updates apply automatically.
- **Separation of concerns**: Orchestrator decides WHEN/WHAT. Agent decides HOW.

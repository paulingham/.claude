# Parallel Dispatch Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/parallel-dispatch-details.md`

## Hybrid Dispatch Model

The pipeline uses two dispatch mechanisms:

| Mechanism | When | Visibility | Cost |
|-----------|------|-----------|------|
| **Subagent** (Agent tool) | Plan, Ship, Deploy, single-slice Build | None (background) | Low (ephemeral) |
| **Team** (TeamCreate) | Multi-slice Build, Review, Final Gate | Tmux split panes | Higher (persistent sessions) |

## Team Phases

### Build Team (conditional -- multi-slice or multi-domain only)

| Scenario | Teammates | Parallel? |
|----------|-----------|-----------|
| Single slice | Subagent (no team) | N/A |
| Multi-slice (independent ACs) | N engineers (1 per slice) | Yes |
| Multi-domain (API + UI + DB) | backend-eng + frontend-eng + db-eng | Yes |

Shut down all engineers after build completes and branches are merged.

### Review Team (always)

| Teammate | When |
|----------|------|
| code-reviewer | Always |
| security-engineer | Always |
| fix-engineer | Spawned into team on CHANGES_REQUESTED, shut down after fix |

Key advantage: reviewer **remembers the codebase** on re-review -- no context reconstruction. On CHANGES_REQUESTED, spawn fix-engineer into the same team, then re-assign review task to the raising reviewer (still alive, still has context).

### Final Gate Team (always)

Three phases run simultaneously instead of sequentially:

| Teammate | Skill | Verdict |
|----------|-------|---------|
| qa-engineer (verify) | `/verify` | VERIFIED |
| qa-engineer (test) | `/qa-test-strategy` | COVERED |
| product-reviewer | `/product-acceptance` | APPROVED |

All three assess the same final state independently. Shut down after all verdicts collected.

## Subagent Phases (unchanged)

| Phase | Why subagent |
|-------|-------------|
| Plan | Read-only, fast, single output |
| Ship | Simple PR creation |
| Deploy | Sequential deploy steps |

## Team Lifecycle

1. `TeamCreate("pipeline-{task-id}")` at pipeline start
2. Spawn teammates just-in-time when their phase begins
3. `TaskCreate` to define work, assign to teammates
4. Teammates read skill files, work, mark tasks complete, go idle
5. `SendMessage({type: "shutdown_request"})` to teammates when phase ends
6. Delete team after pipeline completes

## Teammate Prompt Template

```
Read the skill file at ~/.claude/skills/[name]/SKILL.md and execute it fully.
Also read ~/.claude/skills/[stack]-patterns/SKILL.md for tech-specific guidance if it exists.
Read ~/.claude/agents/[role].md for your full role definition, checklist, and output format.

Context:
- Team: pipeline-{task-id}
- Branch: [branch name]
- Base branch: [main/master]
- Changed files: [from git diff --name-only]
- Full diff: [single git diff output] (review phases only)
- Prior verdict: [previous phase verdict]
- Tech stack: [from project CLAUDE.md]
```

## What This Protocol Is NOT

- **NOT permission to skip skills.** Teammates must read and execute the full skill file.
- **NOT a reason to keep teammates alive across phases.** Shut down after phase completes.
- **NOT a shortcut.** Spawning teammates without skill file references is an anti-pattern.

## Why Hybrid

- **Teams** where parallelism or visibility adds value: Build (multi-slice), Review (parallel + re-review memory), Final Gate (3 phases at once)
- **Subagents** where fire-and-return is sufficient: Plan (quick), Ship (simple), Deploy (sequential)
- **Cost-conscious**: Idle teammates burn tokens. Only team up where it pays off.

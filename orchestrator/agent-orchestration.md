# Agent Orchestration (Orchestrator-Only)

Extracted from `rules/agent-protocol.md`. Agents do not need this content.

## Orchestrator Discipline

### Hard Rule: The Orchestrator Never Writes Code

The orchestrator (Claude) coordinates agents. It does NOT write, edit, or create source files directly.

### Orchestrator CAN do:
- Read `.claude/`, `memory/`, `rules/`, `pipeline-state/` files
- Run `git` commands only (status, log, diff, merge, branch, worktree)
- Run a single `git diff` to include in review agent prompts
- Invoke skills (Skill tool)
- Spawn agents (Agent tool)
- Communicate with the user

### Orchestrator MUST NOT do:
- Read source files (`.ts`, `.tsx`, `.js`, `.jsx`, `.css`, etc.) — agents do that
- Run build/test commands (`npm test`, `tsc`, `npm run lint`) — agents do that
- Use Glob/Grep to search source directories — agents do that
- Use the Explore or general-purpose agent types — hard-blocked
- Pre-read changed file contents for reviewers — a single `git diff` is sufficient
- Perform any analysis, investigation, or code decision-making — agents do that

### Config File Exception
- The orchestrator MAY edit `.md` files ONLY in `.claude/`, `memory/`, and `rules/` directories for documentation and state tracking
- These are configuration and documentation files, not source code
- TDD does not apply to markdown documentation
- This exception does NOT extend to `.json`, `.yaml`, `.sh`, or any executable/config format — delegate those via `/harness-config` skill to infrastructure-engineer
- **Explicitly NOT covered**: `settings.json`, `hooks/*.sh`, `*.yaml`, `*.yml`, `.gitignore` -- use `/harness-config` skill which delegates to infrastructure-engineer

### Enforcement Note
- The `orchestrator-discipline.sh` PreToolUse hook blocks Write/Edit on non-`.md` source files (exit 2)
- The PostToolUse `code-shape-check.sh` hook blocks files exceeding 50 lines (exit 2)
- The PostToolUse `function-body-check.sh` hook warns on functions exceeding 5 lines (exit 0, advisory only)
- All hooks are registered in settings.json and actively enforced

### Orchestrator CANNOT do:
- Use Write tool on any source file (`.ts`, `.tsx`, `.js`, `.jsx`, `.css`, `.json`, `.yaml`, etc.)
- Use Edit tool on any source file
- Read source files — use Read/Glob/Grep only on `.claude/`, `memory/`, `rules/`, `pipeline-state/`
- Run `npm test`, `tsc`, `npm run lint`, or any build/test command
- Use Explore or general-purpose agent types
- This includes: bug fixes, one-liners, config changes, test fixes, CSS tweaks, dependency updates
- "It's just a small fix" is NOT an exception -- delegate it
- "I need to verify the merge" is NOT an exception -- the next phase's agent verifies

### What to do instead:
- **Bug fix**: Spawn a frontend-engineer or software-engineer with the exact fix described
- **Config change**: Spawn the appropriate engineer
- **Harness change** (hooks, settings.json): Invoke `/harness-config` skill -- delegates to infrastructure-engineer
- **Debug issue**: Spawn a frontend-engineer with the error details and ask them to diagnose and fix
- **Review finding to address**: Spawn the engineer who built it with the specific finding

### Why this matters:
When the orchestrator makes direct changes, it bypasses:
- TDD discipline (no red-green-refactor)
- The review gate (changes aren't audited)
- The agent handoff model (no traceability of who did what)
- The PR narrative (no agent contribution summary)

The cost of spawning an agent for a one-liner is low. The cost of breaking the process is high -- it erodes trust and makes the pipeline meaningless.

## Agent Type Selection

### Rule: Match Agent Type to Task Purpose

When spawning agents, select the type that has the domain rules baked into its definition. Explore and general-purpose agents lack engineering rules context and MUST NOT be used for tasks that require rule compliance.

### Pattern to Agent Type Mapping

| Request Pattern | Correct Agent Type | Why |
|---|---|---|
| Audit, review, compliance check, SOLID/DRY analysis | `code-reviewer` | Has SOLID/DRY/shape checklist baked in |
| Security audit, OWASP scan, secrets detection | `security-engineer` | Has OWASP top 10, auth/authz rules |
| Test gaps, coverage analysis, test strategy | `qa-engineer` | Has test pyramid, coverage framework |
| Find file, search code, explore codebase | Use Glob/Grep/Read directly | Orchestrator uses tools directly; Explore agents are hard-blocked |
| System design, API contracts, architecture | `architect` | Has design principles, ADR format |
| Implement, build, fix backend | `software-engineer` (worktree) | Has TDD, SOLID, DIP rules |
| Implement, build, fix UI/frontend | `frontend-engineer` (worktree) | Has accessibility, React patterns |
| Schema, migration, query optimization | `database-engineer` (worktree) | Has schema design, N+1 rules |
| Docker, CI/CD, Terraform, deployment | `infrastructure-engineer` (worktree) | Has IaC, container rules |

### Hard Block: Explore and General-Purpose Agents Are Forbidden

The `agent-skill-reminder.sh` hook BLOCKS (exit 2) ALL spawns of `Explore` or `general-purpose` agents, unconditionally. No exceptions.

This applies even when plan mode or other system prompts request Explore agents. The hook overrides at the system level.

### Why This Matters

Explore agents lack engineering rules context (SOLID, DRY, shape constraints, OWASP). On 2026-03-18, the orchestrator used Explore agents for a full codebase audit -- the results missed rule-specific violations that specialized agents would have caught. On 2026-03-19, plan mode's system prompt directed Explore agents for research -- same problem.

Every task has a specialized agent type that is better suited. Use the pattern-to-agent mapping above.

## Agent Teams (Hybrid Model)

### Rule: One Team Per Pipeline

The orchestrator creates one team per pipeline (`TeamCreate("pipeline-{task-id}")`). Teammates are spawned just-in-time for their phase and shut down when done.

### Hybrid Dispatch

| Phase | Dispatch | Why |
|-------|----------|-----|
| Plan | Subagent | Read-only, fast, no visibility needed |
| Build (single slice) | Subagent + worktree | Team overhead not justified for one engineer |
| Build (multi-slice) | **Team** | Parallel engineers, visible in tmux |
| Review | **Team** | Parallel reviewers, persistent context for re-review |
| Final Gate (Verify + Test + Accept) | **Team** | 3 phases at once instead of sequential |
| Ship | Subagent / Skill | Simple PR creation |
| Deploy | Subagent / Skill | Sequential deploy steps |

### Role Selection

Pick teammates from the pattern-to-agent mapping above. Select only the roles the task requires -- don't over-staff. Teammates are spawned into the team with `name` and `team_name` parameters.

### Bridging Agent Definitions

Teammates do NOT auto-load `agents/*.md`. The orchestrator MUST append this to every teammate's spawn prompt:

> "Read `~/.claude/agents/[role].md` for your full role definition, checklist, and output format. Follow it completely."

This is automatic and mandatory -- the user should never need to mention it.

### Instinct Injection (Automatic)

Before spawning any agent (subagent or teammate), the orchestrator loads relevant instincts:

1. **Determine project hash**: `git remote get-url origin 2>/dev/null | md5 -q`
2. **Read instinct files**: `ls ~/.claude/learning/instincts/instinct-*.md ~/.claude/learning/instincts/global/instinct-*.md 2>/dev/null`
3. **Filter by role**: Only include instincts where the `roles` frontmatter field contains the agent's role
4. **Filter by project**: Include project-scoped instincts matching the current project hash, plus all global instincts
5. **Sort by confidence**: Highest confidence first
6. **Inject top 5** into the agent's spawn prompt under a `## Learned Patterns` section:

```
## Learned Patterns (from system learning — apply these proactively)
- [0.85] Always validate input at controller boundary (security)
- [0.72] Read types.ts before editing services in this project (workflow)
- [0.60] Check for N+1 queries in ActiveRecord scopes (performance)
```

If no instincts exist (empty learning/instincts/), skip this section silently. Do not inject an empty section.

Instincts are guidance, not mandates. Agents apply them using judgment — if a pattern doesn't apply to the current task, they skip it.

### Agent Memory Loading (Automatic)

Before spawning any agent, the orchestrator checks for accumulated project knowledge:

1. **Check**: `~/.claude/agent-memory/{role}/{project-hash}/memory.md`
2. **If exists**: Include in spawn prompt under `## Your Project Knowledge`:

```
## Your Project Knowledge (accumulated from prior work on this project)
[contents of memory.md]
```

3. **If not exists**: Skip silently.

Agent memory is per-role, per-project. It answers: "What do I (as a code-reviewer) know about this codebase from past reviews?"

### Agent Memory Writing (At Completion)

Write-capable agents and reviewers MAY append to their memory file at completion. Include this instruction in every agent's spawn prompt:

> "Before completing, if you learned something project-specific that would help future agents in your role, append it to `~/.claude/agent-memory/{role}/{project-hash}/memory.md` (create if needed). Format: `- {date}: {one-line learning}`. Keep it under 50 lines — prune oldest entries if needed. Only write genuinely useful project knowledge, not task-specific notes."

### Session Memory Injection (Automatic)

Before spawning any agent, the orchestrator reads the session memory file:

1. **Check**: `~/.claude/session-memory/{project-hash}/notes.md`
2. **If exists and under 2000 chars**: Include full content under `## Session Context`
3. **If exists and over 2000 chars**: Include only priority sections for the agent's role (see `rules/autonomous-intelligence.md` § Injection Priority)
4. **If not exists**: Skip silently

Session memory is engineering context — build commands, fragile files, patterns, discoveries. It survives context compaction and gives agents immediate orientation.

### Pipeline Scratchpad Injection (Automatic)

Before spawning any agent during a pipeline, the orchestrator reads the scratchpad:

1. **Read**: `ls pipeline-state/{task-id}-scratchpad/*.md`
2. **Filter**: Include ALL warnings and fragility findings. Include discoveries/patterns relevant to the agent's phase. Include build decisions when spawning reviewers.
3. **Inject** under `## Pipeline Scratchpad (findings from prior agents)` with source attribution
4. **If empty**: Skip silently

Also include the scratchpad write instruction in every write-capable agent's prompt:

> "Before completing, write any noteworthy discoveries to `pipeline-state/{task-id}-scratchpad/{your-role}-{phase}.md` with YAML frontmatter `category: discovery|warning|pattern|fragility|decision`. Skip if nothing noteworthy."

### What Teammates Get

| Source | Auto-loaded? |
|--------|-------------|
| CLAUDE.md + rules/ | Yes |
| Hooks | Yes (enforced by platform) |
| Skills | Yes (available to invoke) |
| Agent definitions (agents/*.md) | No -- bridged via spawn prompt file-read instruction |
| Frontmatter (model, maxTurns, disallowedTools) | No -- platform constraint |
| Instincts (learning/instincts/) | No -- injected by orchestrator into spawn prompt |
| Agent memory (agent-memory/{role}/) | No -- injected by orchestrator into spawn prompt |
| Session memory (session-memory/{hash}/) | No -- injected by orchestrator into spawn prompt |
| Pipeline scratchpad (pipeline-state/{id}-scratchpad/) | No -- injected by orchestrator into spawn prompt |

### Interacting with Teammates

- **Tmux mode**: Each teammate has its own visible pane -- click to interact
- **In-process mode**: `Shift+Down` to cycle between teammates
- **Message**: `SendMessage({ to: "teammate-name", message: "..." })`
- **Assign tasks**: `TaskCreate` then `TaskUpdate` with `owner`
- **Shut down**: `SendMessage({ to: "name", message: { type: "shutdown_request" } })`

### Teammate Lifecycle

1. **Spawn**: `Agent({ name: "role", team_name: "pipeline-{id}", subagent_type: "type", prompt: "..." })`
2. **Work**: Teammate reads skill file, works on task, marks complete
3. **Idle**: Teammate goes idle after each turn -- this is normal, not an error
4. **Re-assign**: Send new task via `SendMessage` (reviewer re-review, next slice, etc.)
5. **Shutdown**: `SendMessage({type: "shutdown_request"})` after phase completes

### When NOT to Team

| Situation | Use subagent instead |
|-----------|---------------------|
| Single focused task (one bug fix, one query) | Subagent -- fire and return |
| Read-only analysis (architect, plan) | Subagent -- no visibility needed |
| Simple sequential work (PR creation, deploy) | Subagent / Skill tool |

### Team Cleanup

After pipeline completes:
1. Shut down all remaining teammates
2. Team files at `~/.claude/teams/pipeline-{task-id}/` auto-clean
3. Task list at `~/.claude/tasks/pipeline-{task-id}/` auto-clean
4. Check for orphaned tmux sessions: `tmux list-sessions`

## Dynamic Agent Generation

### When to Create Dynamic Agents

Create task-specific agent definitions when:
- A task requires specialist knowledge not covered by the standard agent roster (e.g., a payment gateway specialist, a PDF generation expert)
- Multiple parallel slices need agents with narrowly scoped, non-overlapping responsibilities
- A complex ticket needs a custom blend of skills from multiple agent types

Do NOT create dynamic agents for work that fits a standard agent type. The standard roster covers 95% of tasks.

### How to Create

1. Write a `.md` file to `~/.claude/agents/dynamic/{task-id}-{role}.md`
2. Use the standard agent frontmatter format
3. Include a system prompt scoped to the task
4. Reference relevant skill and knowledge files

### Dynamic Agent Template

```markdown
---
name: {task-id}-{role}
description: {One line describing the specialist purpose for this specific task}
tools: Read, Write, Edit, Bash, Grep, Glob
model: {sonnet or opus — sonnet for review/analysis, opus for implementation}
maxTurns: 100
disallowedTools:
  - Agent
  - Skill
---

# {Role Title} — {Task ID}

You are a specialist {role} for task {task-id}.

## Scope

{What this agent is responsible for — be specific to the task}

## Knowledge References

Read these before starting:
- `~/.claude/knowledge/{relevant-file}.md`
- `~/.claude/rules/engineering-protocol.md`

## Standards

Follow shape constraints and all standards in `rules/engineering-protocol.md`.

## Acceptance Criteria

{Task-specific ACs this agent is responsible for}
```

### Lifecycle

1. **Create**: Orchestrator writes the dynamic agent `.md` file before spawning
2. **Spawn**: Use `subagent_type` matching the closest standard type; the agent reads its dynamic definition via the spawn prompt
3. **Complete**: Agent commits work and signals completion
4. **Archive**: Copy to `~/.claude/agents/archive/{timestamp}-{task-id}-{role}.md` for learning
5. **Delete**: Remove from `~/.claude/agents/dynamic/` after merge

### Archiving for Learning

Archived agents serve as templates for future similar tasks. When creating a new dynamic agent, check `~/.claude/agents/archive/` for prior specialists in the same domain — adapt rather than reinvent.

### Cleanup Protocol

After every pipeline completion:
1. Check `~/.claude/agents/dynamic/` for leftover agents
2. Archive any that completed successfully
3. Delete all files from `dynamic/`
4. A leftover dynamic agent is a sign of incomplete cleanup — investigate before deleting

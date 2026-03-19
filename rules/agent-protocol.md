# Agent Protocol

Consolidates: agent worktree protocol, agent type selection, orchestrator discipline.

## Orchestrator Discipline

### Hard Rule: The Orchestrator Never Writes Code

The orchestrator (Claude) coordinates agents. It does NOT write, edit, or create source files directly.

### Orchestrator CAN do:
- Read files (Read, Glob, Grep)
- Run commands (tests, linting, git, npm)
- Invoke skills (Skill tool)
- Spawn agents (Agent tool)
- Communicate with the user

### Config File Exception
- The orchestrator MAY edit `.md` files in `.claude/`, `memory/`, and `rules/` directories
- These are configuration and documentation files, not source code
- TDD does not apply to markdown documentation
- This exception does NOT extend to `.json`, `.yaml`, `.sh`, or any other non-markdown format -- delegate those via `/harness-config`
- **Explicitly NOT covered**: `settings.json`, `hooks/*.sh`, `*.yaml`, `*.yml` -- use `/harness-config` skill which delegates to infrastructure-engineer

### Enforcement Note
- The `orchestrator-discipline.sh` PreToolUse hook blocks Write/Edit on non-`.md` source files (exit 2)
- The PostToolUse `code-shape-check.sh` hook blocks files exceeding 50 lines (exit 2)
- The PostToolUse `function-body-check.sh` hook warns on functions exceeding 5 lines (exit 1)
- All hooks are registered in settings.json and actively enforced

### Orchestrator CANNOT do:
- Use Write tool on any source file (`.ts`, `.tsx`, `.js`, `.jsx`, `.css`, `.json`, `.yaml`, etc.)
- Use Edit tool on any source file
- This includes: bug fixes, one-liners, config changes, test fixes, CSS tweaks, dependency updates
- "It's just a small fix" is NOT an exception -- delegate it

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
| Find file, search code, explore codebase | `Explore` | Fast codebase navigation |
| System design, API contracts, architecture | `architect` | Has design principles, ADR format |
| Implement, build, fix backend | `software-engineer` (worktree) | Has TDD, SOLID, DIP rules |
| Implement, build, fix UI/frontend | `frontend-engineer` (worktree) | Has accessibility, React patterns |
| Schema, migration, query optimization | `database-engineer` (worktree) | Has schema design, N+1 rules |
| Docker, CI/CD, Terraform, deployment | `infrastructure-engineer` (worktree) | Has IaC, container rules |

### Hard Block: Explore and General-Purpose Agents Are Forbidden

The `agent-skill-reminder.sh` hook BLOCKS (exit 2) ALL spawns of `Explore` or `general-purpose` agents, unconditionally. No exceptions.

This applies even when plan mode or other system prompts request Explore agents. The hook overrides at the system level.

### Why This Matters

Explore agents lack engineering rules context (SOLID, DRY, shape constraints, OWASP). On 2026-03-18, the orchestrator used Explore agents for a full codebase audit — the results missed rule-specific violations that specialized agents would have caught. On 2026-03-19, plan mode's system prompt directed Explore agents for research — same problem.

Every task has a specialized agent type that is better suited. Use the pattern-to-agent mapping above.

## Agent Teams

### Rule: Teammates Must Read Their Agent Definition

Agent Team teammates do NOT auto-load agent definitions from `agents/*.md`. When creating a team, instruct each teammate to read its role file:

> "You are the [role] on this team. Read ~/.claude/agents/[role].md for your full checklist and output format. Follow it completely."

### What Teammates Get Automatically

- CLAUDE.md and all `rules/` files (auto-loaded)
- Hooks (enforced by platform)
- Skills (available to invoke)

### What Teammates Do NOT Get (must bridge via file read)

- Agent definition content from `agents/*.md` (role-specific checklists, output formats)
- Frontmatter settings: model, maxTurns, disallowedTools (platform constraint, not bridgeable)

### How to Start a Team

Teams are created via natural language — just describe what you want:

> "Create a team: a software-engineer to build the API, a frontend-engineer for the UI, and a code-reviewer to audit both. Each should read their agent definition from ~/.claude/agents/."

The orchestrator creates the team, spawns teammates, and sets up a shared task list. Teammates work independently and communicate with each other directly.

### Interacting with Teammates

- **Cycle teammates**: `Shift+Down` (in-process mode)
- **Message a teammate**: cycle to them and type
- **Assign tasks**: tell the lead to create tasks for specific teammates
- **Shut down**: ask the lead to shut down a teammate
- **Clean up**: "Clean up the team" removes all shared resources

### When to Use Teams vs Sub-agents

| Use | Mechanism | Why |
|-----|-----------|-----|
| Pipeline phases (build, review, verify, test, accept) | Sub-agents via skills | Full enforcement: agent definitions, frontmatter guardrails, skill protocols |
| Parallel exploration, design debates | Agent Teams | Teammates communicate directly, challenge each other |
| Multi-domain coordination (frontend + backend + DB) | Agent Teams | Shared task list, independent work with messaging |
| Focused single task (bug fix, one review) | Sub-agent | Simpler, faster, full definition loaded automatically |

## Worktree Isolation

### Rule: Write-Capable Agents Use Worktree Isolation

When the orchestrator spawns agents that will create or modify files, it MUST use `isolation: "worktree"` to give the agent an isolated copy of the repository.

### Write-Capable Agents (MUST use worktree)

- **software-engineer**: Backend features, business logic, TDD
- **frontend-engineer**: UI, accessibility, React/React Native
- **qa-engineer**: Test strategy, integration/E2E test authoring
- **database-engineer**: Schema, migrations, query optimization
- **infrastructure-engineer**: Docker, CI/CD, Terraform, deployment

### Read-Only Agents (NO worktree needed)

- **code-reviewer**: PR review, SOLID/DRY/security audit
- **security-engineer**: OWASP, auth, secrets, dependency scanning
- **product-reviewer**: AC validation, UX, business value
- **architect**: System design, API contracts, slice decomposition

### Spawning Pattern

```
// Write-capable agent -- ALWAYS include isolation
Agent({
  subagent_type: "frontend-engineer",
  isolation: "worktree",
  prompt: "..."
})

// Read-only agent -- no isolation needed
Agent({
  subagent_type: "code-reviewer",
  prompt: "..."
})
```

### Parallel Worktrees

Independent work MUST run in parallel worktrees:
- Multiple engineers implementing independent slices -> separate worktrees, spawned in a single message
- Code reviewer + security engineer -> parallel (no worktrees needed, read-only)
- QA writing tests for independent features -> separate worktrees

### Why Worktrees Matter

- Prevents agents from stepping on each other's changes
- Allows true parallel execution without merge conflicts
- Each agent gets a clean working tree
- Changes are isolated until explicitly merged
- If an agent's work is rejected, the worktree is simply discarded

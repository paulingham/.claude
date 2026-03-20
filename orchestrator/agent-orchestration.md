# Agent Orchestration (Orchestrator-Only)

Extracted from `rules/agent-protocol.md`. Agents do not need this content.

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

Explore agents lack engineering rules context (SOLID, DRY, shape constraints, OWASP). On 2026-03-18, the orchestrator used Explore agents for a full codebase audit -- the results missed rule-specific violations that specialized agents would have caught. On 2026-03-19, plan mode's system prompt directed Explore agents for research -- same problem.

Every task has a specialized agent type that is better suited. Use the pattern-to-agent mapping above.

## Agent Teams

### Rule: Orchestrator Always Creates Teams

The orchestrator creates an Agent Team for ALL implementation tasks. The user never needs to request a team or specify roles -- just describe the work.

### Role Selection

The orchestrator picks teammates from the pattern-to-agent mapping above. Select only the roles the task requires -- don't over-staff.

### Bridging Agent Definitions

Teammates do NOT auto-load `agents/*.md`. The orchestrator MUST append this to every teammate's spawn prompt:

> "Read `~/.claude/agents/[role].md` for your full role definition, checklist, and output format. Follow it completely."

This is automatic and mandatory -- the user should never need to mention it.

### What Teammates Get

| Source | Auto-loaded? |
|--------|-------------|
| CLAUDE.md + rules/ | Yes |
| Hooks | Yes (enforced by platform) |
| Skills | Yes (available to invoke) |
| Agent definitions (agents/*.md) | No -- bridged via spawn prompt file-read instruction |
| Frontmatter (model, maxTurns, disallowedTools) | No -- platform constraint |

### Interacting with Teammates

- **Cycle**: `Shift+Down` (in-process mode)
- **Message**: cycle to a teammate and type
- **Assign tasks**: tell the lead to create tasks
- **Shut down**: ask the lead to shut down a teammate
- **Clean up**: "Clean up the team" when done

### Teams vs Sub-agents

| Use | Mechanism |
|-----|-----------|
| Pipeline phases (build, review, verify, test, accept, ship) | Sub-agents via skills |
| Parallel exploration, design debates, multi-domain coordination | Agent Teams |
| Focused single task (bug fix, one review, one query) | Sub-agent |

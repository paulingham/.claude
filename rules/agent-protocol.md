# Agent Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/agent-orchestration.md`

## Orchestrator Does Not Write Code

The orchestrator coordinates agents. It does NOT write, edit, or create source files directly. This is why you (as an agent) are being spawned -- all implementation, fixes, and config changes go through agents.

**Config exception**: The orchestrator MAY edit `.md` files in `.claude/`, `memory/`, and `rules/` directories. This does NOT extend to `.json`, `.yaml`, `.sh`, or any other non-markdown format.

## Worktree Isolation

### Rule: Write-Capable Agents Use Worktree Isolation

When the orchestrator spawns agents that will create or modify files, it MUST use `isolation: "worktree"` to give the agent an isolated copy of the repository.

### Write-Capable Agents (MUST use worktree)

- **software-engineer**, **frontend-engineer**, **qa-engineer**, **database-engineer**, **infrastructure-engineer**

### Read-Only Agents (NO worktree needed)

- **code-reviewer**, **security-engineer**, **product-reviewer**, **architect**

### Parallel Worktrees

Independent work MUST run in parallel worktrees:
- Multiple engineers implementing independent slices -> separate worktrees, spawned in a single message
- Code reviewer + security engineer -> parallel (no worktrees needed, read-only)
- QA writing tests for independent features -> separate worktrees

## Worktree Commit Protocol

Agents working in worktrees MUST commit their work before completing:
1. Stage all changed files: `git add` specific files (not `git add .`)
2. Commit with a descriptive message including: what was built, test count, any known issues
3. If work is incomplete (approaching turn limit): commit with `WIP:` prefix
4. The orchestrator merges worktree branches via `git merge` or `git cherry-pick`
5. Never leave uncommitted changes in a worktree -- uncommitted work cannot be merged reliably

## Continuation From WIP

When an agent's prior attempt was committed as WIP, the orchestrator includes in the continuation prompt:
- The WIP commit message (lists completed and remaining work)
- `git log --oneline -3` output (to orient the agent)
- Do NOT re-explain the full feature spec — the agent reads existing code and tests
- The continuation agent runs tests first to confirm the WIP state is green

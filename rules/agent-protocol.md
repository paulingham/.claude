# Agent Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/agent-orchestration.md`

## Orchestrator Does Not Write Code

> **IRON LAW: THE ORCHESTRATOR NEVER WRITES SOURCE CODE. NO EXCEPTIONS.**

The orchestrator coordinates agents. It does NOT write, edit, or create source files directly. This is why you (as an agent) are being spawned -- all implementation, fixes, and config changes go through agents.

**Config exception**: The orchestrator MAY edit `.md` files ONLY in `.claude/`, `memory/`, and `rules/` directories for documentation and state tracking. This does NOT extend to `.json`, `.yaml`, `.sh`, or any executable/config format — delegate those via `/harness-config` skill to infrastructure-engineer.

### Pressure-Aware Enforcement

The orchestrator has violated source-file discipline under time pressure in multiple sessions:
- Debugging cycles where "just this one quick edit" felt faster than spawning an agent
- Interactive loops where the user was waiting for a fix

**These are exactly the moments discipline matters most.** The 30 seconds saved by a direct edit:
- Sets a precedent that erodes the entire agent model
- Produces unreviewed code on the critical path
- Has been called out by the user multiple times

If agent overhead is genuinely blocking iteration, **propose a process change to the user** — do not silently bypass.

## Isolation: Worktrees vs Teams

### Subagent Phases: Worktree Isolation

When the orchestrator spawns **subagents** that will create or modify files, it MUST use `isolation: "worktree"`.

- **Write-capable subagents** (MUST use worktree): software-engineer, frontend-engineer, qa-engineer, database-engineer, infrastructure-engineer
- **Read-only subagents** (NO worktree): code-reviewer, security-engineer, product-reviewer, architect

### Team Phases: Branch Isolation

When teammates are spawned into the pipeline team, they manage their own branches:
- Each write-capable teammate creates a feature branch (e.g., `build/{task-id}-{slice}`)
- Teammates commit to their branch before completing
- The orchestrator merges branches after the phase completes
- Read-only teammates (reviewers, product-reviewer) work on the main branch

### Parallel Work

- **Subagents**: Multiple worktrees spawned in a single message
- **Team**: Multiple teammates spawned in a single message, each on their own branch
- Code reviewer + security engineer -> team (visible in tmux, persistent for re-review)
- QA + product-reviewer -> team (final gate, parallel)

## Commit Protocol

All agents (subagents in worktrees AND teammates on branches) MUST commit before completing:
1. Stage all changed files: `git add` specific files (not `git add .`)
2. Commit with a descriptive message including: what was built, test count, any known issues
3. If work is incomplete (approaching turn limit): commit with `WIP:` prefix
4. The orchestrator merges branches via `git merge` or `git cherry-pick`
5. Never leave uncommitted changes -- uncommitted work cannot be merged reliably

## Agent Memory Protocol

Agents accumulate per-project knowledge in `agent-memory/{role}/{project-hash}/memory.md`. This is institutional knowledge — what the agent has learned about a specific codebase across pipelines.

### Writing Memory
Before completing, if the agent learned something project-specific:
1. Check if `~/.claude/agent-memory/{role}/{project-hash}/memory.md` exists (create directory + file if not)
2. Append: `- {YYYY-MM-DD}: {one-line learning}`
3. Keep under 50 lines — prune oldest entries if file exceeds limit
4. Only write genuinely useful project knowledge, not task-specific notes

### What to Remember
- Project conventions not in CLAUDE.md (e.g., "this project uses barrel exports")
- Recurring patterns (e.g., "auth module has complex session lifecycle — read session.ts first")
- Known fragile areas (e.g., "payment webhook handler is timing-sensitive")
- Build/test quirks (e.g., "tests require DATABASE_URL set, not mocked")

### What NOT to Remember
- Task-specific details ("added login button to header")
- Information already in project CLAUDE.md
- Temporary state that won't apply next time

## Continuation From WIP

When an agent's prior attempt was committed as WIP, the orchestrator includes in the continuation prompt:
- The WIP commit message (lists completed and remaining work)
- `git log --oneline -3` output (to orient the agent)
- Do NOT re-explain the full feature spec — the agent reads existing code and tests
- The continuation agent runs tests first to confirm the WIP state is green

## Worktree Lifecycle (subagent phases)

After merging a worktree branch:
1. Remove the worktree: `git worktree remove .claude/worktrees/agent-XXXX --force`
2. Delete the branch: `git branch -d worktree-agent-XXXX`
3. Verify with `git worktree list` — only the main worktree should remain

Never leave stale worktrees — they consume disk space and confuse test runners.

## Teammate Lifecycle (team phases)

Teammates are spawned just-in-time and shut down after their phase:
1. **Spawn**: Orchestrator uses `Agent` with `team_name` and `name` parameters
2. **Work**: Teammate reads skill file, creates branch, implements, commits
3. **Complete**: Teammate marks task complete via `TaskUpdate`, goes idle
4. **Shutdown**: Orchestrator sends `SendMessage({type: "shutdown_request"})` after phase
5. **Merge**: Orchestrator merges the teammate's branch, deletes it

Never keep teammates alive across phases — idle teammates burn tokens.
Stale teammates from failed pipelines need manual cleanup (`tmux kill-session` if needed).

## Dynamic Agents

For complex tasks requiring specialist knowledge beyond the standard roster, the orchestrator can generate task-specific agents. See `~/.claude/orchestrator/agent-orchestration.md` § Dynamic Agent Generation for the full protocol.

- Dynamic agents live in `agents/dynamic/` and are deleted after use
- Archived in `agents/archive/` for future reference
- Always use the standard agent template (see orchestrator doc)
- Dynamic agents follow all the same rules: worktree isolation, commit protocol, shape constraints

## Shell Environment

Agent shells may not inherit the user's version manager (nvm, rbenv, pyenv, rustup, etc.).

Before running build/test commands, agents MUST:
1. Check if the command exists: `which npm` / `which bundle` / `which python` (or equivalent)
2. If not found, source the user's shell profile: `source ~/.zshrc 2>/dev/null || source ~/.bashrc 2>/dev/null`
3. If still not found, report the error — do not retry blindly

The project CLAUDE.md's Commands section is the source of truth for how to run tests.
If commands fail with "command not found", check the project CLAUDE.md first.

## Fresh Verification Requirement

> **IRON LAW: NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.**

Before any agent signals completion (BUILD_COMPLETE, VERIFIED, etc.):
1. Run the full test suite NOW — not "tests passed earlier"
2. Run the type checker NOW — not "tsc passed when I last ran it"
3. Stale output from earlier in the session is NOT evidence
4. If you cannot run verification commands, report this — do not claim completion

"I ran the tests 50 turns ago" is not verification. Run them again.

## Dependency Management

The orchestrator MUST NOT run `npm install`, `bundle add`, `pip install`, or any package manager command. These modify `package.json`, lock files, and `node_modules/` — all of which are source/build artifacts.

**Who installs dependencies:**
- **Build agents** install dependencies as part of their implementation work (in their worktree)
- **Infrastructure engineers** install tool-level dependencies as part of scaffold work (in their worktree)

**Orchestrator's role:**
- Identify required dependencies during planning (from architect output or task requirements)
- Include dependency requirements in the build agent's prompt
- The build agent installs, verifies, and commits dependency changes in its worktree

**Why:** `npm install` modifies the main working tree. If the orchestrator runs it, the main tree becomes dirty, conflicting with worktree-based agents. Dependencies installed in the main tree are NOT available in worktrees (which inherit from the git index). Dependencies are build artifacts — they go through agents.

## Test Runner Isolation

Worktrees are created inside `.claude/worktrees/` within the project directory.
Test runners that use directory discovery (Jest, pytest, rspec, go test) WILL find
test files in worktrees, causing duplicate runs and false failures.

After the FIRST worktree creation in any project, verify the test runner's config
excludes `.claude/worktrees/`. Add exclusion if missing:
- **Jest**: `testPathIgnorePatterns: ["/.claude/worktrees/"]` in jest.config
- **pytest**: `testpaths = ["tests"]` in pyproject.toml (explicit paths, not discovery)
- **rspec**: `--exclude-pattern '.claude/**'` in .rspec
- **Go**: Module-scoped by default (no issue unless using recursive `./...`)
- **Other**: Add equivalent exclusion for the project's test runner

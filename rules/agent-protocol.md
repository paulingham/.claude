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

## Pipeline Scratchpad Protocol

Agents share findings within a pipeline run via the scratchpad. See `rules/autonomous-intelligence.md` for full details.

### Reading (On Spawn)
The orchestrator injects scratchpad findings into the agent's prompt. Agents do not read the scratchpad directory directly — the orchestrator curates what's relevant.

### Writing (Before Completion)
Before completing, write discoveries to `pipeline-state/{task-id}-scratchpad/{role}-{phase}.md`. Use YAML frontmatter with `category: discovery|warning|pattern|fragility|decision`. Only write genuinely useful findings, not task narration. If nothing noteworthy was discovered, skip this step.

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

For the harness-of-harness case (session worktrees of `$HOME/.claude` created by `scripts/new-session.sh`), see `knowledge/session-isolation-patterns.md` for which state is shared via symlinks vs per-branch.

## Main-Branch Invariant

> **IRON LAW: REPO_ROOT HEAD STAYS ON `main` FOR THE ENTIRE DURATION OF EVERY PIPELINE RUN.**

Every git mutation that would move HEAD runs against a *worktree path*, expressed via an explicit delegation prefix in the command string. This is what allows multiple Claude Code sessions to coexist on the same physical clone without branch-state stomping.

### Forbidden bare forms (caught by `hooks/main-branch-guard.sh`)

- `git checkout <branch>` / `git checkout -b <branch>`
- `git switch <branch>` / `git switch -c <branch>`
- `git branch -d <name>` / `git branch -D <name>`
- `git reset --hard ...`
- `git merge <ref>`
- `git rebase <upstream>`
- `git pull` (any args)
- `git fetch <remote> <src>:<local-dst>` (refspec writing a local ref, e.g. `main:main`, `pull/123/head:pr-123`)
- `git push <remote> <src>:main` (writing remote main)
- `gh pr create ...`

### Allowed delegated forms

- `git -C <worktree-path> <cmd>`
- `git --git-dir=<worktree-path>/.git <cmd>`
- `cd <worktree-path> && <cmd>`
- `(cd <worktree-path> && <cmd>)`

`;`-separator does NOT count as delegation. `cd /tmp/x; git checkout foo` is **forbidden** — the `;` separator does not compose semantically with `cd` to guarantee the second clause runs in the new cwd. Only `&&` does. (Mechanically: `split_clauses` splits on `;` too, so a standalone `git checkout foo` clause is evaluated on its own and rejected as a bare form.) Use `&&` or the `git -C` / `git --git-dir=` flags.

### Always allowed (any cwd, any form)

Read-only ops (`git status|log|diff|show|rev-parse|describe|blame`), `git fetch <remote>` without refspec, `git fetch --all`, refspecs that write only `refs/remotes/...`, `git worktree {add,list,remove,prune}`, `git push <remote> <branch>` to non-main destinations, `git add|commit|tag|notes`.

### How agents must operate

- Agents always have a worktree assigned by the orchestrator. The path is in the spawn prompt.
- Mutate via `git -C "$WORKTREE" <cmd>` or `(cd "$WORKTREE" && <cmd>)`. Never type a bare HEAD-moving command.
- The `gh pr create` call runs INSIDE a `(cd "$WORKTREE" && ...)` wrapper. If you find yourself typing a bare `gh pr create`, stop — the guard will block it.

### Verification

At any observation point in any session:

```bash
git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD
```

must return `main`. The `main-branch-guard.sh` PreToolUse Bash hook prevents violations dynamically; the `worktree-cwd-check.sh` SubagentStop hook diagnoses any violation that slipped through (post-hoc forensics + drift detection).

### Why this matters

The harness-of-harness model lets the user spawn parallel sessions via `scripts/new-session.sh`, each in its own worktree under `$HOME/.claude-sessions/`. Those worktrees share state directories with REPO_ROOT (per `knowledge/session-isolation-patterns.md`). If REPO_ROOT HEAD moves, every concurrent session's git operations start fighting for the same branch — pull/fetch/merge become non-deterministic, eval baselines stamp against the wrong SHA, trajectory writers and observation-capture log against the wrong commit graph, and the human user sees "why is HEAD on `feature/foo`?!".

### Why command-shape inspection (not cwd inspection)

The guard inspects the COMMAND STRING the agent literally typed, not the cwd of the spawned Bash process. The harness reliably exposes `tool_input.command` (every existing Bash hook in the codebase reads it); it does NOT reliably expose `tool_input.cwd` for subagent calls (no existing hook in this codebase reads it). Command-shape is a single source of truth: agents either type a delegated form (allowed) or a bare form (forbidden), with no hidden state to chase. This makes the rule decidable from the command string alone, with no per-process cwd resolution.

Trade-off accepted: bare `git checkout foo` is forbidden universally — even from inside a worktree. Inside a worktree the agent must still write `git -C "$WORKTREE" checkout foo` (or `cd "$WORKTREE" && git checkout foo`). This is tighter than strictly necessary, and it is intentional: it makes the rule trivially auditable from the command string alone.

### Enforcement hooks

- `hooks/main-branch-guard.sh` — PreToolUse Bash hook. Inspects `tool_input.command`, blocks (exit 2) any forbidden bare form, logs to `metrics/$SESSION/main-branch-violations.jsonl` with `source: "prevented"`.
- `hooks/worktree-cwd-check.sh` — SubagentStop hook. Re-confirms prevented violations and detects drift (`git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD != "main"`), appending `source: "post-confirmed"` and `source: "drift-detected"` records. Diagnostic only — never blocks.

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

## Internal Eval Gate (harness changes)

PRs that modify ANY of the following directories MUST run `/internal-eval run` and produce zero regressions before merge:
- `rules/`
- `hooks/`
- `skills/`
- `agents/`

The agent opening the PR is responsible for invoking `/internal-eval run`. The verdict must be `EVAL_PASSED` (zero regressions on deterministic cases). `EVAL_FAILED` blocks merge.

`eval/` changes themselves do NOT trigger this gate (would be circular).

Exceptions:
- Docs-only changes to `.md` files outside of SKILL.md / agent definitions: gate may be skipped with an explicit note in the PR body.
- Emergency fixes with incident ticket reference: gate may be deferred with explicit post-merge commitment to re-run.

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

## Resource Bounds

The harness caps subagent recursion depth and per-job wall-clock time so no
pipeline can run away. Caps live in the `settings.json` `env` block (single
source of truth):

| Bound | Default | Env override |
|-------|---------|--------------|
| Subagent recursion depth | 3 | `CLAUDE_SUBAGENT_MAX_DEPTH` |
| Subagent wall-clock | 1800s | `CLAUDE_SUBAGENT_MAX_RUNTIME` |
| Teammate wall-clock | 3600s | `CLAUDE_TEAMMATE_MAX_RUNTIME` |

**Enforcement hooks:**

- `hooks/depth-guard.sh` (PreToolUse Agent): refuses spawn when
  `CLAUDE_SUBAGENT_DEPTH >= max`. Top-level orchestrator (variable unset)
  is treated as depth 0. Logs `metrics/$SID/depth-violations.jsonl` with
  `record_type:"depth_violation"`, `depth`, `max_depth`, `subagent_type`,
  `task_id`, `action:"prevented"`. Exit 2 on block.
- `hooks/runtime-guard.sh` (PreToolUse Agent|Bash|Write|Edit; Read
  excluded — high-volume, fast-bounded). Mode A on Agent records
  `metrics/$SID/subagent-runtimes/<key>.start` (idempotent — first-seen
  timestamp wins). Mode B on Bash|Write|Edit performs an orchestrator-level
  global scan and emits a shutdown directive on stderr (exit 2) for any
  start-file whose elapsed time exceeds the per-class cap. No
  `CLAUDE_SUBAGENT_ID` dependency — Option C global scan reads start-file
  bodies (`<unix_ts>:<class>:<display>`) for stderr enrichment. Logs
  `metrics/$SID/runtime-violations.jsonl`.
- `hooks/subagent-stop-trajectory.sh` — extended on SubagentStop to delete
  the matching `<key>.start` file, preventing stale-timestamp false
  positives on re-spawn with the same key. Shared SHA1 derivation via
  `_lib/runtime-guard-key.sh`.

**Shutdown semantics by class** (honest Path-B disclosure):

- **Teammate** (`team_name` non-empty): stderr block is the exact
  `SendMessage({type:"shutdown_request", name:"<display>"})` form,
  directly actionable per `## Teammate Lifecycle (team phases)` above.
- **Non-team subagent**: stderr says "next tool call blocked; orchestrator
  should re-dispatch per rules/operational-protocol.md". No equivalent
  out-of-band kill exists in the current Agent tool input schema; the
  next tool the runaway subagent attempts is refused at PreToolUse, the
  orchestrator interprets the violation log, and decides re-dispatch
  (retry-twice-then-escalate). Mirrors the `pre-agent-thinking.sh` Path-B
  precedent — a degraded-but-correct enforcement today, one-line flip
  when the API surface lands.

**Depth propagation contract:** orchestrators MUST set
`CLAUDE_SUBAGENT_DEPTH = parent_depth + 1` in the shell that invokes Agent
before each spawn. The child inherits the variable via process env. See
`orchestrator/agent-orchestration.md > § Spawn Procedure` and
`orchestrator/parallel-dispatch-details.md > § Team Dispatch` for the
literal example bash assignment.

**Forensics:** `metrics/$SID/depth-violations.jsonl` and
`metrics/$SID/runtime-violations.jsonl` join on `session_id` + `task_id`
for retroactive auditing of cap breaches.

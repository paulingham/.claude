# Agent Orchestration (Orchestrator-Only)

Extracted from `protocols/agent-protocol.md`. Agents do not need this content.

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
- This exception does NOT extend to `.json`, `.yaml`, `.sh`, or any executable/config format — delegate those via `/harness:harness-config` skill to infrastructure-engineer
- **Explicitly NOT covered**: `settings.json`, `hooks/*.sh`, `*.yaml`, `*.yml`, `.gitignore` -- use `/harness:harness-config` skill which delegates to infrastructure-engineer

### Enforcement Note
- The `orchestrator-discipline.sh` PreToolUse hook blocks Write/Edit on non-`.md` source files (exit 2)
- The PostToolUse `code-shape-check.sh` hook blocks files exceeding 50 lines (exit 2)
- The PostToolUse `function-body-check.sh` hook warns on functions exceeding 8 lines (exit 0, advisory only)
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
- **Harness change** (hooks, settings.json): Invoke `/harness:harness-config` skill -- delegates to infrastructure-engineer
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

### Thinking Injection (Automatic)

The `pre-agent-thinking.sh` PreToolUse hook is currently **advisory/log-only**: the Agent tool input schema does not yet expose `thinking`, so the hook resolves the defaults and records them but does NOT block any spawn. Behavior:

- **Missing `thinking` field on an Agent spawn**: hook exits 0 and logs the resolved `{effort, display}` to `metrics/{session}/hook-injections.jsonl` with `source: "logged"`. No stderr block. No refusal.
- **Present `thinking` field**: hook exits 0, no validation.
- **Non-Agent tools**: hook exits 0 immediately.

Operators inspect `metrics/{session}/hook-injections.jsonl` to see what defaults the hook would have applied for any given spawn.

**Forward pointer**: When Claude Code lands `modified_tool_input` for hook returns (Path A) or the Agent tool input schema exposes `thinking`, the hook's enforcement layer flips. The resolver, tests, and precedence rules are unchanged.

See `protocols/thinking-defaults.md` § Hook Behavior for the full precedence table and field semantics.

### Tool Allowlist Auto-Derivation (Automatic)

The orchestrator's spawn template should attempt to populate `tool_input.allowed_tools` from the spawned `subagent_type`'s frontmatter `tools:` array, when feasible. The intent: every spawn carries the narrowest tool surface its role declares — no Bash on read-only reviewers, no Agent on engineers — without the orchestrator hand-listing tools per call.

Today this is **advisory** because the Agent tool input schema does not yet expose `allowed_tools`. The `pre-agent-allowlist.sh` PreToolUse hook reads the spawned `subagent_type`, loads the role's frontmatter `tools:` via `agent_tools_loader`, and computes a subset check against any caller-provided `tool_input.allowed_tools`. Any superset request is logged to `metrics/{session}/tool-allowlist.jsonl` with `source: "path-b-advisory"`. No spawn is refused.

Once the Agent input schema lands `allowed_tools`, this flips to enforcement: requests outside the role's frontmatter allowlist exit 2 at PreToolUse with `action: would_block` and the spawn is refused. The hook is the only file that changes — the loader, the role frontmatter, and the metrics shape stay put.

**Override**: `CLAUDE_DISABLE_TOOL_ALLOWLIST=1` is a per-session escape hatch (hook fast-exits). Useful when a spawn legitimately needs a wider surface than its role declares — record the rationale in the pipeline scratchpad.

**Reference**: `protocols/agent-protocol.md` § Per-Agent Tool Scoping for the full contract (frontmatter shape, subset semantics, metrics fields).

### Instinct Injection (every Agent spawn)

Before invoking `Agent(...)`, the orchestrator MUST resolve and splice the `## Learned Patterns` block into the spawn prompt body. The hook (`hooks/instinct-injector.sh`) is **advisory/log-only** today — it cannot mutate the prompt because the Agent input schema does not yet expose `modified_tool_input`. The orchestrator-side splice IS the actual delivery mechanism. See `protocols/autonomous-intelligence.md` § Instinct Injection for the selection algorithm, JSONL forensic format, and Path-B disclosure surface.

#### Caller contract

1. **Resolve the project hash**:

   ```bash
   source ~/.claude/hooks/_lib/project-hash.sh
   PROJECT_HASH=$(_project_hash --fallback "local")
   ```

2. **Load instincts and resolve for the spawn target** — the canonical implementation lives in three modules under `hooks/_lib/`:

   ```python
   import sys
   sys.path.insert(0, "hooks/_lib")
   from instinct_loader import load_instincts
   from instinct_injector import resolve_for_agent
   from agent_parent_chain import load_expanded_instinct_categories
   from agent_min_confidence_loader import load_min_confidence

   instincts = load_instincts(PROJECT_HASH)
   cats = load_expanded_instinct_categories(subagent_type) or []
   # Per-agent frontmatter `min_confidence:` overrides env + default;
   # falls back to env→default (0.4) when the agent declares nothing.
   floor = load_min_confidence(subagent_type)
   block = resolve_for_agent(subagent_type, cats, instincts,
                             floor_override=floor)
   ```

   Or invoke the entry script `hooks/_lib/resolve-instincts.py` directly (the same script the hook uses) and read its `RESOLVED {json}` line for the rendered block plus telemetry.

3. **Splice when non-empty**: if `block != ""`, insert it into the spawn prompt at the `## Learned Patterns (from system learning)` insertion point documented in `protocols/parallel-dispatch-protocol.md` § Teammate Prompt Template. The block sits between the `Context:` block and the `## Session Context` block — this position is unchanged. Note: the upstream persona-end marker (string anchor, immediately after the three persona-read instructions in the template; the literal marker string lives canonically in the Teammate Prompt Template — see that file for the exact bytes) is a documented future contract for the unbuilt `cache_control` breakpoint hook. The current orchestrator splice continues to use the `## Learned Patterns` section-header text as its anchor; downstream tooling that DOES locate the persona-end marker MUST do so by string match rather than line offset, since line numbers are unstable across template re-paginations. If `block == ""`, omit the section silently — do not inject an empty header.

4. **Write the orchestrator-injected JSONL record** (Path-B disclosure surface). After the spawn-prompt write succeeds, append to `metrics/{session-id}/instinct-injections.jsonl`:

   ```json
   {"timestamp":"...","source":"orchestrator-injected",
    "agent_role":"<subagent_type>",
    "resolved":{"hook_record_ts":"...","count_injected":N,
                "subagent_type":"...","task_id":"..."}}
   ```

   The hook writes a paired `source: "logged"` record on every spawn for forensic visibility — these are NOT a substitute for orchestrator-side injection. A `logged` record without a paired `orchestrator-injected` record (same session, same `subagent_type` + `task_id`) is a Path-B failure surfaced by `/harness:forensics`.

#### Output format

```
## Learned Patterns (from system learning — apply these proactively)
- [0.85] Always validate input at controller boundary (security)
- [0.72] Read types.ts before editing services in this project (workflow)
- [0.60] Check for N+1 queries in ActiveRecord scopes (performance)
```

Bullet template: `- [{confidence:.2f}] {pattern_summary} ({domain})`. The `pattern_summary` is the first non-empty line of the instinct's `## Pattern` body, truncated at 200 chars. Empty result after filtering → returns `""` (orchestrator skips the section silently).

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

Before spawning any agent, the orchestrator resolves the role's sub-file list from `hooks/_lib/session_memory_role_resolver.py` (`resolve_subfiles_for_role(role)`) and reads each via `session_memory_read_split` so legacy single-file content is still tolerated during the 30-day DUAL_PATH soak:

1. **Resolve**: `subs = resolve_subfiles_for_role("$AGENT_ROLE")` — returns an ordered list of basenames (`active-work` is NEVER in the list — orchestrator-only).
2. **For each sub-file**: read via `session_memory_read_split $PROJECT_HASH $sub`. New layout wins; legacy section extracted from the single-file fallback otherwise.
3. **Empty-body skip**: when `should_inject_subfile(text)` returns False (body < 50 chars after stripping header + italic description + blank lines), omit that sub-file from the rendered block.
4. **Concatenate** under `## Session Context (engineering notes for this project)`, each sub-file preceded by a `### {sub-file}` heading.
5. **If not exists for any sub-file**: skip silently.

Session memory is engineering context — build commands, fragile files, patterns, discoveries. It survives context compaction and gives agents immediate orientation.

### Session Memory Update (Backend Sync Wrap)

When session memory needs updating after a pipeline phase, the orchestrator dispatches **N parallel `session-memory-updater` agents in a single message**, one per affected sub-file (max N = 4 — `active-work.md` is excluded; the orchestrator writes that file directly via `session_store_put`). Each updater agent is Edit-only (no `Bash` tool grant), preserving the Path B per-agent tool-allowlist invariant. The orchestrator wraps the parallel spawn with backend round-trip helpers from `hooks/_lib/session-store.sh`.

Per the C3 split, each spawn receives `targetFile` (path to ONE sub-file) and `targetSection` (the basename: `codebase-map`, `build-test`, `patterns`, or `fragility`). Sub-files NOT mentioned in this pipeline's facts remain untouched — no Edit lock contention, no spurious version-bumps. The dispatch helper at `hooks/_lib/session-memory-updater-dispatch.sh` enforces the input contract: `targetFile` and `targetSection` MUST both be non-blank, otherwise the spawn is refused with a structured `{error,...}` JSONL line on stderr. The helper also performs **seed-on-miss**: if `targetFile` does not exist on disk, it is created from `session-memory/config/templates/{targetSection}.md` before the spawn proceeds — required because the updater is Read+Edit-only and cannot create the file itself. Seeding emits a `{"info":"seeded_from_template",...}` line on stderr so first-run misses are observable.

Canonical wrap template (orchestrator-side bash) — note the parallel spawns in a single message and the directory-scoped sync wrap:

```bash
source "$HOME/.claude/hooks/_lib/session-store.sh"
PROJ_DIR="$HOME/.claude/session-memory/$PROJECT_HASH"
session_memory_sync_in "$PROJECT_HASH" "$PROJ_DIR"   # backend → directory (no-op for local)

# active-work.md: orchestrator writes directly, no updater spawn.
printf '%s\n' "$active_work_body" | session_store_put "$PROJECT_HASH" active-work -

# Spawn N parallel updaters in a single message (one per affected sub-file).
# Each spawn carries its own targetFile + targetSection. The orchestrator's
# dispatch loop calls session-memory-updater-dispatch.sh as a guard before
# emitting each Agent call.
# Example for two affected sub-files:
#   Agent({ subagent_type: "session-memory-updater",
#           prompt: "targetFile=$PROJ_DIR/build-test.md  targetSection=build-test ..." })
#   Agent({ subagent_type: "session-memory-updater",
#           prompt: "targetFile=$PROJ_DIR/patterns.md    targetSection=patterns ..." })

session_memory_sync_out "$PROJECT_HASH" "$PROJ_DIR"  # directory → backend (no-op for local)
```

`sync_in` materialises remote blobs (one per canonical sub-file, or template stamp on first-run miss) into the project directory. `sync_out` mirrors each sub-file back. For `BACKEND=local` (default), both helpers are byte-no-ops — zero behaviour change. For `BACKEND=s3` / `BACKEND=redis`, the helpers loop over the 5 canonical basenames (`codebase-map`, `build-test`, `patterns`, `fragility`, `active-work`); each sub-file is stored under `subkey == basename`. PUT failures emit a JSONL forensic line via `log-injection.sh` and exit 0 so the workflow never blocks on durability. See `protocols/autonomous-intelligence.md` § Adapters and § Sub-file Layout & Soak, plus `session-memory/adapters/README.md` for the full contract.

**Reader-fallback during the 30-day DUAL_PATH soak**: the injection path uses `session_memory_read_split $hash $sub` (defined in `hooks/_lib/session-memory-read-split.sh`). For each sub-file the helper returns the new-layout file when present, falling back to the canonical section of the legacy single-file otherwise. Each fallback hit appends a forensic JSONL line at `metrics/{session-id}/session-store-mirror.jsonl` with `source: "session-memory-read-fallback"` so soak-window misses are observable.

### Pipeline Scratchpad Injection (Automatic)

Before spawning any agent during a pipeline, the orchestrator reads the scratchpad and applies a **category-based relevance filter** so each spawn only sees findings that bear on its phase. This keeps prompt size bounded and prevents irrelevant noise from drowning load-bearing warnings.

1. **Read**: `ls $state_dir/{task-id}/scratchpad/*.md` (workstream variant: `$state_dir/workstreams/{ws}/{task-id}/scratchpad/*.md`). During the DUAL_PATH soak (see `protocols/pipeline-protocol.md` § Structured Pipeline State), the legacy form `$state_dir/{task-id}-scratchpad/*.md` is still tolerated.
2. **Filter** by category × spawn target:

   | Finding category | Forwarded to |
   |------------------|--------------|
   | `warning` | ALL subsequent phases (every spawn after the writer) |
   | `fragility` | ALL subsequent phases (every spawn after the writer) |
   | `discovery` | Next immediate phase only (e.g. build → review, then dropped) |
   | `pattern` | Same role on subsequent phases only (e.g. software-engineer pattern → next software-engineer spawn; never to product-reviewer) |
   | `decision` | Reviewers (`code-reviewer`, `security-engineer`) and Final Gate roles (`qa-engineer`, `product-reviewer`, `patch-critic`) only |

   The phase ordering used to compute "subsequent" follows the canonical pipeline: Plan → Build → Review → Verify → Test → Accept → Patch-Critique → Ship → Deploy. The writer's `{phase}` field on the scratchpad file determines provenance.
3. **Inject** the filtered set under `## Pipeline Scratchpad (findings from prior agents)` with source attribution `[role/phase] category: …`. Findings are listed by category, fragility/warnings first.
4. **If the filtered set is empty**: skip the section silently — no header, no placeholder.

Also include the scratchpad write instruction in every write-capable agent's prompt:

> "Before completing, write any noteworthy discoveries to `$state_dir/{task-id}/scratchpad/{your-role}-{phase}.md` with YAML frontmatter `category: discovery|warning|pattern|fragility|decision`. Skip if nothing noteworthy."

**Forensics**: the `scratchpad-bytes.sh` PreToolUse hook (Agent matcher) measures the bytes of scratchpad content visible to each spawn after filtering and logs to `metrics/{session-id}/scratchpad-bytes.jsonl`. Use this to spot regressions (a phase suddenly seeing 10x more bytes) or under-injection (warnings dropped because the filter was misapplied).

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
| Pipeline scratchpad ($state_dir/{id}/scratchpad/) | No -- injected by orchestrator into spawn prompt |

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

## Worktree Env Propagation (Automatic)

The orchestrator MUST set `$CLAUDE_WORKTREE_PATH` on every Build-onward Agent dispatch (Build, Code Review, Security Review, Final Gate, Ship, Deploy). For agents without a worktree (orchestrator-context: `code-reviewer`, `security-engineer`, `patch-critic`, `product-reviewer`, `pr-creation`), the env points at the Build-phase worktree that produced the candidate diff.

Failure to propagate yields `metrics/{session}/freshness-guard.jsonl` records with `reason: "no_worktree_resolvable"` — operators read these as orchestrator drift, NOT legitimate skips.

This contract is the load-bearing fallback for HEAD resolution in `hooks/verification-freshness-guard.sh` (`rules/core.md` Iron Law 2 enforcement at v2.1.141 advisory + post-promotion blocking).

**Cross-references**: `rules/core.md` § Iron Law 2; `protocols/_proposals/2026-05-14-iron-law-2-freshness-hook.md` § Promotion Criterion.

## Spawn Procedure

Every Agent spawn (subagent or teammate) propagates `CLAUDE_SUBAGENT_DEPTH`
through the spawn shell so `hooks/depth-guard.sh` can refuse runaway
recursion. Top-level orchestrator: leave the variable unset (treated as 0).
For each spawn, set `CLAUDE_SUBAGENT_DEPTH = parent_depth + 1` in the spawn
shell — the child inherits it via process env, the next-level depth-guard
reads it, and any spawn that would cross the cap (default 3) is refused at
PreToolUse with a structured stderr block.

Example (orchestrator-side spawn shell):

```bash
# parent_depth comes from the orchestrator's own env (unset → 0).
parent_depth="${CLAUDE_SUBAGENT_DEPTH:-0}"
child_depth=$((parent_depth + 1))
CLAUDE_SUBAGENT_DEPTH=$child_depth Agent \
  --subagent_type=software-engineer \
  --isolation=worktree \
  --prompt="..."
```

The literal `CLAUDE_SUBAGENT_DEPTH=<N>` assignment is the load-bearing piece —
it must appear in the shell that invokes the Agent tool, not merely in
surrounding prose. See `protocols/parallel-dispatch-protocol.md > Resource
Bounds` for caps, env overrides, and refusal semantics. The mechanism mirrors
the Path-B precedent in `pre-agent-thinking.sh`: documentation-first
discipline today, automatic injection when the Agent tool input schema
exposes env-var passing.

### Executor Resolution

The executor model that backs each Agent spawn is no longer a flat per-agent
constant. The orchestrator resolves it at spawn time by walking three
precedence layers, top-down — the first match wins:

1. **`CLAUDE_FORCE_OPUS=1` env override** — if the env var is set to `"1"`
   in the orchestrator shell, the resolver returns `claude-opus-4-7`
   regardless of the agent's declared `executor:` field. This is the
   operator escape hatch for spawns requiring monolithic Opus reasoning
   (architecturally complex slices, ambiguous spec interpretation, recovery
   from a problematic Sonnet build). `CLAUDE_FORCE_OPUS=1` is session-scoped, not pipeline-scoped — operators must re-export the env var per session. It does not persist across `/exit` and does not narrow to a specific pipeline run; every spawn in the session that follows the export sees the override.
2. **`prefer_opus: true` instinct match** — when an instinct file in
   `learning/{project-hash}/instincts/*.md` carries `prefer_opus: true` and
   the instinct's `roles:` set intersects the spawning agent's expanded
   `instinct_categories`, the resolver returns `claude-opus-4-7` for that
   spawn. Trigger: `/harness:learn` is expected to set `prefer_opus: true` when ≥3
   pipelines in the same project show a Sonnet executor requiring ≥2 review
   rounds. **Not yet implemented — orchestrator reader deferred to the next learning slice. Manually-authored instincts may set the flag, but the orchestrator does not yet consume it.**
3. **Frontmatter `executor:` field** — the default. After Wave 5/B6 the
   `software-engineer` and `frontend-engineer` agents resolve to
   `claude-sonnet-4-6`; reviewer/QA roles already resolved this way prior
   to the wave. The frontmatter is the floor, not a ceiling.

The resolver lives at `hooks/_lib/executor_resolver.py::resolve_executor`.
It is called by orchestrator-side spawn code, not by a PreToolUse hook —
the Agent input schema does not currently expose `modified_tool_input`, so
a hook today would be log-only (Path-B precedent of `pre-agent-thinking.sh`).
A `pre-agent-executor.sh` hook is reserved for promotion when the schema
lands.

### Model Self-Tuning Notes

After Wave 5/B6, `software-engineer` and `frontend-engineer` are
**Sonnet-default with Opus advisor**. Routine ATDD-cycle build work runs on
Sonnet; the advisor is consulted on judgement calls (architectural choices,
ambiguous spec interpretation, accessibility tradeoffs for FE). Opus is
available via two routes: (a) `CLAUDE_FORCE_OPUS=1` for one-off operator
escalation; (b) a `prefer_opus: true` instinct for data-driven escalation
once `/harness:learn` writes the flag (deferred). The other tunable agents
(`database-engineer`, `infrastructure-engineer`, `qa-engineer`) keep their
prior model selection — see the Agent Team table in `CLAUDE.md` for the
canonical per-role default.

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
tools:
  - Read
  - Write
  - Edit
  - Bash
  - Grep
  - Glob
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
- `~/.claude/protocols/engineering-invariants.md`
- `~/.claude/protocols/atdd-procedure.md` (build/fix phases)

## Standards

Follow shape constraints and all standards in `protocols/engineering-invariants.md`. For build phases, also follow `protocols/atdd-procedure.md`.

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

## Pressure-Aware Enforcement (Orchestrator Discipline)

The orchestrator has violated source-file discipline under time pressure in multiple sessions:

- Debugging cycles where "just this one quick edit" felt faster than spawning an agent
- Interactive loops where the user was waiting for a fix
- **The Bash bypass**: Edit tool blocked → pivot to `Bash(python3 -c "open(...'w')")` or `sed -i` to write the same file. This is the same violation via a different tool. The hook catches Write/Edit; the iron law covers ALL write paths.

These are exactly the moments discipline matters most. The 30 seconds saved by a direct edit:

- Sets a precedent that erodes the entire agent model
- Produces unreviewed code on the critical path
- Has been called out by the user multiple times

If a tool-level block fires (Edit blocked by `orchestrator-discipline.sh`), that is the system working correctly. The response is to invoke `/harness:harness-config` — not to find a Bash equivalent. If agent overhead is genuinely blocking iteration, propose a process change to the user — do not silently bypass.

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

## Dependency Management (orchestrator side)

The orchestrator MUST NOT run `npm install`, `bundle add`, `pip install`, or any package manager command. These modify `package.json`, lock files, and `node_modules/` — all of which are source/build artifacts.

**Who installs dependencies:**

- **Build agents** install dependencies as part of their implementation work (in their worktree)
- **Infrastructure engineers** install tool-level dependencies as part of scaffold work (in their worktree)

**Orchestrator's role:**

- Identify required dependencies during planning (from architect output or task requirements)
- Include dependency requirements in the build agent's prompt
- The build agent installs, verifies, and commits dependency changes in its worktree

**Why:** `npm install` modifies the main working tree. If the orchestrator runs it, the main tree becomes dirty, conflicting with worktree-based agents. Dependencies installed in the main tree are NOT available in worktrees (which inherit from the git index). Dependencies are build artifacts — they go through agents.

## Test Runner Isolation (first-worktree-in-project setup)

Worktrees are created inside `.claude/worktrees/` within the project directory. Test runners that use directory discovery (Jest, pytest, rspec, go test) WILL find test files in worktrees, causing duplicate runs and false failures.

After the FIRST worktree creation in any project, verify the test runner's config excludes `.claude/worktrees/`. Add exclusion if missing:

- **Jest**: `testPathIgnorePatterns: ["/.claude/worktrees/"]` in jest.config
- **pytest**: `testpaths = ["tests"]` in pyproject.toml (explicit paths, not discovery)
- **rspec**: `--exclude-pattern '.claude/**'` in .rspec
- **Go**: Module-scoped by default (no issue unless using recursive `./...`)
- **Other**: Add equivalent exclusion for the project's test runner

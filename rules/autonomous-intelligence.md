# Autonomous Intelligence Protocol

Three systems that make the pipeline self-improving: agents share knowledge in real-time, engineering context survives compaction, and the system gets better at building YOUR project with every run.

## 1. Pipeline Scratchpad

Cross-agent knowledge sharing within a single pipeline run. Agents discover things (fragile files, working patterns, environment quirks). Instead of that knowledge dying with the agent, it flows forward to every subsequent agent.

### Directory

```
pipeline-state/{task-id}-scratchpad/
  {role}-{phase}.md          # Agent findings
```

Created by the orchestrator at pipeline start (alongside the pipeline state file). Cleaned up with pipeline state after completion.

### Agent Writes

Every write-capable agent appends findings before completion. Include this in every agent's spawn prompt:

> "Before completing, write any discoveries to the pipeline scratchpad at `pipeline-state/{task-id}-scratchpad/{your-role}-{phase}.md`. Format below. Only write genuinely useful findings — not task narration."

Finding format:

```markdown
---
category: discovery|warning|pattern|fragility|decision
---

{One to three sentences. Be specific: name files, functions, error messages.}
```

Categories:
- **discovery**: Something learned about the codebase ("this project uses barrel exports", "auth module has complex session lifecycle")
- **warning**: Something dangerous or surprising ("payment webhook handler is timing-sensitive", "test suite requires DATABASE_URL")
- **pattern**: A working approach ("the composition pattern X→Y→Z works well here", "always read types.ts before editing services")
- **fragility**: Something that breaks easily ("CSS hiding on WebView containers hides dynamic children", "config parsing has no validation")
- **decision**: A design choice made with rationale ("chose service object over standalone function because of shared SDK dependency")

### Orchestrator Injects

Before spawning each agent, the orchestrator reads the scratchpad directory and injects relevant findings into the agent's prompt:

```
## Pipeline Scratchpad (findings from prior agents in this pipeline)
- [build/software-engineer] discovery: This project uses barrel exports in src/index.ts
- [build/software-engineer] warning: Tests require DATABASE_URL set, not mocked
- [build/software-engineer] decision: Used service object for AuthService (shared SDK dep)
```

**Injection rules:**
- Include ALL warnings and fragility findings (these prevent mistakes)
- Include discoveries and patterns relevant to the agent's phase
- Include decisions from the build phase when spawning reviewers (context for review)
- Skip findings from the same role re-spawned (they already know)
- If scratchpad is empty, skip the section silently

### Why Scratchpad, Not Agent Memory

Agent memory (`agent-memory/{role}/`) persists across pipelines — it's institutional knowledge. The scratchpad is ephemeral — it's THIS pipeline's knowledge. Build agent discovers a quirk → reviewer needs to know NOW, not next pipeline.

## 2. Session Memory

Engineering context that survives context compaction. Not conversation notes — **codebase knowledge**: what builds, what tests, what's fragile, what patterns work.

### Location

```
~/.claude/session-memory/{project-hash}/notes.md
```

Project hash: source `hooks/_lib/project-hash.sh` and call `_project_hash --fallback "local"`. The helper picks `md5sum` on Linux and falls back to `openssl dgst -md5` on macOS (portable across both OSes without relying on mac-specific `openssl` flags).

### Template

The template lives at `~/.claude/session-memory/config/template.md`. Sections are engineering-focused, not conversation-focused. Each section has an italic description that MUST be preserved during updates.

### Lifecycle

1. **Creation**: On first pipeline in a project, create the notes file from template if it doesn't exist
2. **Updates**: After each pipeline phase completes, the orchestrator spawns a `session-memory-updater` agent (Read/Edit only, Haiku, read-only of conversation context) to update session memory with new engineering context
3. **Injection**: Before spawning any agent, include the session memory content:

```
## Session Context (engineering notes for this project)
[contents of session-memory/{project-hash}/notes.md]
```

4. **Compaction survival**: The notes file persists on disk. After context compaction, `/pipeline-resume` re-reads it automatically. This is the primary mechanism for maintaining coherence across long runs.

### Update Trigger

Update session memory when ANY of these are true:
- A pipeline phase just completed (new engineering knowledge likely)
- Context compaction is about to happen (preserve what we know)
- The user provides significant codebase context (architecture, conventions, quirks)

Do NOT update after every tool call or every turn. Updates are expensive (spawning a Haiku agent). Batch them at phase boundaries.

### Update Mechanism

Spawn a `session-memory-updater` agent (Agent tool, `subagent_type: session-memory-updater`, `run_in_background: true`). The agent:
- Reads the current notes file at `notesPath`
- Updates sections with new engineering knowledge handed to it by the orchestrator
- Uses Edit tool — preserves structure (never touches `#` headers or `_italic_` descriptions)
- Runs in background — does not block the pipeline
- Terminates after emitting `SESSION_MEMORY_UPDATED: {path}`

The orchestrator's spawn prompt MUST include:
- `notesPath`: absolute path to `~/.claude/session-memory/{project-hash}/notes.md`
- A curated bulleted list of engineering facts from the just-completed phase (files, commands, patterns, PRs, gotchas). Do NOT dump raw conversation — hand over distilled facts.
- Reference to `~/.claude/agents/session-memory-updater.md` for its full role definition.

The legacy prompt template at `~/.claude/session-memory/config/prompt.md` remains as a reference for what content belongs in each section.

### Injection Priority

When injecting session memory into agent prompts, prioritize sections by agent role:

| Agent Role | Priority Sections |
|---|---|
| software-engineer, frontend-engineer | Build & Test, Critical Paths, Patterns |
| code-reviewer, security-engineer | Critical Paths, Patterns, Session Discoveries |
| qa-engineer | Build & Test, Critical Paths, Active Work |
| infrastructure-engineer | Build & Test, Environment |
| architect | Codebase Map, Patterns, Critical Paths |

If the full notes file is under 2000 chars, inject it all. If larger, inject only priority sections for the role.

### Adapters

Session memory storage is pluggable behind a five-function adapter contract (`session_store_put|get|delete|list|list_subkeys`) plus two sync helpers (`session_memory_sync_in|out`) sourced from `hooks/_lib/session-store.sh`. The contract surface is documented in full at `session-memory/adapters/README.md`. Three backends ship today:

- `local` (default) — on-disk markdown file under `~/.claude/session-memory/{project_hash}/{session_id}.md`. Zero observable behaviour change vs. pre-adapter harness.
- `s3` — shells out to `aws s3 cp/ls/rm`. Whole-blob writes (no append).
- `redis` — shells out to `redis-cli SET/GET/DEL/KEYS`. Whole-blob writes.

Selection env vars:

| Variable | Required | Default | Notes |
|---|---|---|---|
| `CLAUDE_SESSION_STORE_BACKEND` | no | `local` | One of `local`, `s3`, `redis` |
| `CLAUDE_SESSION_STORE_BUCKET` | when `BACKEND=s3` | — | S3 bucket |
| `CLAUDE_SESSION_STORE_REDIS_URL` | when `BACKEND=redis` | — | e.g. `redis://host:6379/0` |
| `CLAUDE_SESSION_STORE_PREFIX` | no | `sessions/` | **IGNORED by local adapter**; applies only to s3/redis |

Fallback policy: env-var check FIRST, then required-env validation, then `command -v` for the CLI. On any failure of validation or tool-availability, the resolver emits a one-line stderr warning AND a JSONL forensic line via `log-injection.sh`, then falls back to `local`. Resolution is cached per-process in the exported shell var `_SESSION_STORE_RESOLVED_BACKEND` (NOT a file sentinel — file sentinel would stomp across parallel pipelines with different BACKEND values).

`sessionId` is currently always `notes`; per-pipeline or per-agent notes would change call sites only — the contract already supports them.

Caller wiring: `session-memory-updater` stays Edit-only (no Bash grant). The orchestrator wraps its spawn with `session_memory_sync_in` BEFORE and `session_memory_sync_out` AFTER, per `orchestrator/agent-orchestration.md` § Session Memory Update. For `BACKEND=local`, both helpers are byte-no-ops — default-local behaviour is byte-identical to pre-adapter.

## 3. Continuous Learning Loop

The system gets better at building YOUR project with every pipeline. Not manual — automatic.

### Observation Capture (Every Pipeline)

After every pipeline completion (in the Reflect step), write a structured observation:

```bash
# Append to learning/{project-hash}/observations.jsonl
{
  "record_type": "pipeline",
  "timestamp": "ISO 8601",
  "session_id": "...",
  "pipeline_id": "{task-id}",
  "classification": "feature|refactor|bug",
  "phases": {
    "build": {"verdict": "BUILD_COMPLETE", "rounds": 1, "agents": 2},
    "review": {"verdict": "APPROVE", "rounds": 2, "findings": 3},
    "verify": {"verdict": "VERIFIED", "tiers_passed": 3},
    "test": {"verdict": "COVERED", "coverage": 92},
    "accept": {"verdict": "APPROVED", "conditions": 0}
  },
  "scratchpad_findings": ["list of category:summary from scratchpad"],
  "rework": false,
  "duration_phases": 6,
  "complexity_budget": 9
}
```

### Consolidation Gate

The auto-learn gate is enforced by the `auto-learn-gate.sh` Stop hook. It fires a visible context message telling the orchestrator to invoke `/learn` when ALL conditions are met:
- ≥3 pipeline observations (`record_type == "pipeline"`) since the last `/learn` run
- ≥3 pipelines since the last `/learn` run, OR no `/learn` has ever run in this project, OR ≥24 hours have elapsed since the last run
- Current pipeline (by `task_id`) is not the one that triggered the most recent firing (idempotency)

Counters are persisted at `~/.claude/learning/{project-hash}/.learn-state.json`. The hook reads only newly-appended observations via a file-offset cursor, so it is idempotent across multiple Stop-event firings within the same turn. The `/learn` skill resets `pipelines_since_learn` and `observations_since_learn` to 0 and stamps `last_learn_run` when it completes (see `skills/learn/SKILL.md` Step 10).

Why a hook (not a checklist item): orchestrator memory is unreliable across long runs; the hook fires deterministically on every model-turn end.

**Escape hatch**: set `CLAUDE_DISABLE_AUTO_LEARN=1` in the environment to suppress gate firings (hook fast-exits). Useful for debugging or bulk-work sessions where you want to batch learning manually.

### Feedback Loop

```
Pipeline Run → Observation Captured → Gate Check
                                         ↓ (gate met)
                                    /learn invoked
                                         ↓
                              Instincts created/updated
                                         ↓
                              Next pipeline agents receive
                              instincts in their prompts
                                         ↓
                              Better build → fewer review rounds
                              → stronger instincts → ...
```

### Scratchpad → Instinct Promotion

Scratchpad findings that recur across 3+ pipelines should be promoted to instincts. The `/learn` skill detects this by comparing scratchpad findings (captured in observations) across pipeline runs:

- Same discovery/warning appearing in 3+ pipelines → create instinct with confidence 0.3
- Same fragility appearing in 3+ pipelines → create instinct with confidence 0.5 (fragilities are high-value)
- Same pattern validated across 3+ pipelines → create instinct with confidence 0.4

## 4. Prompt Tracing (Optional)

Debugging aid for agent failures: capture the exact rendered prompt the orchestrator sent to a spawn — skills, instincts, session memory, scratchpad, agent memory, all already composed into `tool_input.prompt` by the orchestrator.

### Enabling

- `CLAUDE_ENABLE_TRACE=1` in the environment enables tracing
- Unset or `0` (default) = zero overhead — the hook's first line fast-exits

### Location and Format

- Path: `~/.claude/metrics/{session-id}/trace/{role}-{task-id}-{timestamp}.txt`
- Role is sanitized (`/` and `:` replaced with `-`), so a Skill trace lands at `skill-{name}-...`
- File layout (three sections, always present):
  ```
  == SPAWN METADATA ==
  timestamp, session_id, task_id, agent_role, model, phase, dispatch, worktree
  == RENDERED PROMPT ==
  {full prompt body or skill args}
  == END ==
  ```

### Retention

- 7 days; pruned on SessionStart by `hooks/trace-cleanup.sh`
- Empty trace/session dirs removed after prune

### Privacy Warning

Traces are local-only and may contain sensitive prompt content. Never commit the `metrics/` directory — `.gitignore` already excludes it via the allowlist default.

## Integration Points

### Pipeline Pre-flight (additions to existing protocol)

After existing pre-flight steps:
1. Create scratchpad directory: `mkdir -p pipeline-state/{task-id}-scratchpad/`
2. Read session memory: `cat session-memory/{project-hash}/notes.md`
3. Check auto-learn gate: count observations since last `/learn`

### Agent Spawn (additions to existing protocol)

Every agent spawn prompt now includes (in order):
1. Skill file reference (existing)
2. Agent definition reference (existing)
3. Instinct injection (existing)
4. Agent memory (existing)
5. **Session memory injection** (NEW — engineering context)
6. **Scratchpad injection** (NEW — this pipeline's findings)
7. **Scratchpad write instruction** (NEW — contribute back)

### Pipeline Reflect (additions to existing protocol)

After existing reflection steps:
1. **Capture observation** to `learning/{project-hash}/observations.jsonl`
2. **Check auto-learn gate** — invoke `/learn` if met
3. **Update session memory** — spawn `session-memory-updater` agent with latest engineering context (background, non-blocking)
4. **Clean up scratchpad** — deleted with pipeline state

### Pipeline Resume (additions to existing protocol)

When resuming a pipeline:
1. Read session memory (primary orientation mechanism)
2. Read scratchpad (pick up where agents left off)
3. Continue from current phase with full context

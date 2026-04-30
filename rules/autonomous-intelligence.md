# Autonomous Intelligence Protocol

Three systems that make the pipeline self-improving: agents share knowledge in real-time, engineering context survives compaction, and the system gets better at building YOUR project with every run.

## 1. Pipeline Scratchpad

Cross-agent knowledge sharing within a single pipeline run. Agents discover things (fragile files, working patterns, environment quirks). Instead of that knowledge dying with the agent, it flows forward to every subsequent agent.

### Directory

```
pipeline-state/{task-id}/scratchpad/
  {role}-{phase}.md          # Agent findings
```

Workstream variant: `pipeline-state/workstreams/{ws}/{task-id}/scratchpad/{role}-{phase}.md`.

Created by the orchestrator at pipeline start (alongside the pipeline state file). Cleaned up with `rm -rf pipeline-state/{task-id}/` after completion. During the DUAL_PATH soak (see `rules/pipeline-protocol.md` § Structured Pipeline State), the legacy form `pipeline-state/{task-id}-scratchpad/` is still tolerated by readers; new pipelines write to the new layout only.

### Agent Writes

Every write-capable agent appends findings before completion. Include this in every agent's spawn prompt:

> "Before completing, write any discoveries to the pipeline scratchpad at `pipeline-state/{task-id}/scratchpad/{your-role}-{phase}.md`. Format below. Only write genuinely useful findings — not task narration."

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

### Instinct Injection (Path-B advisory)

The PreAgent hook `hooks/instinct-injector.sh` (registered on the `Agent` matcher at PreToolUse position 6, between `pre-agent-allowlist.sh` and `depth-guard.sh`) computes which instincts apply to each spawn target and records the resolution to `metrics/{session-id}/instinct-injections.jsonl` for forensic visibility. The hook is **advisory/log-only today**: the Agent tool input schema does not yet expose `modified_tool_input`, so the hook cannot patch the spawn prompt. Actual `## Learned Patterns` injection into the prompt body is performed by the orchestrator at spawn time (see `orchestrator/agent-orchestration.md` § Spawn Procedure / § Instinct Injection). When `modified_tool_input` lands, only `hooks/instinct-injector.sh` flips behaviour — resolver, loader, agent frontmatter, and the orchestrator-caller contract are unchanged.

#### Selection algorithm

1. **Load instincts** from `learning/{project-hash}/instincts/*.md` (project-scoped) and `learning/instincts/*.md` (global), via `hooks/_lib/instinct_loader.py`. Per-file failures are skipped with a `source: "load-warning"` JSONL record — the loader never raises.
2. **Filter by role**: keep instincts whose `roles:` set intersects the spawning agent's `instinct_categories:` set (per-agent frontmatter, loaded by `hooks/_lib/agent_instinct_categories_loader.py`).
3. **Filter by confidence floor**: drop any instinct with `confidence < CLAUDE_INSTINCT_MIN_CONFIDENCE` (default `0.4`).
4. **Dedup by `id`**: when the same `id` appears in both project and global directories, the project entry wins (project beats global).
5. **Sort and cap**: sort by `confidence` DESC, secondary sort by `id` ASC for stability, then keep the top `CLAUDE_INSTINCT_TOP_N` (default `5`; `0` produces an empty block).

The actionable summary in each rendered bullet comes from the `## Pattern` body of the instinct file (first non-empty line, truncated at 200 chars), NOT from a frontmatter field.

#### Per-agent `instinct_categories:` contract

Every file in `agents/*.md` declares an `instinct_categories:` YAML list of role-name tokens. An instinct matches an agent IFF `set(instinct.roles) ∩ set(agent.instinct_categories) != ∅`. The full per-role mapping lives in `tests/test_agent_instinct_categories.py` as a snapshot — any frontmatter drift fails CI. The list MUST be a YAML list (not a comma-separated string); regression test `tests/test_learn_roles_enforcement.py` locks the contract in both directions.

#### JSONL forensic format

Path: `metrics/{session-id}/instinct-injections.jsonl`. Three distinct `source` values:

| `source` | Emitter | When |
|---|---|---|
| `logged` | `hooks/instinct-injector.sh` | Every Agent spawn — records `count_kept`, `count_rejected_by_floor`, `count_rejected_by_role`, `top_ids`, `min_confidence`, `top_n`, `instinct_categories` |
| `load-warning` | `hooks/_lib/instinct_loader.py` | Per-file load failure — records `file:` and `reason:` (one of: `malformed-yaml`, `missing-confidence-field`, `missing-roles-field`, `missing-or-empty-pattern-body`) |
| `orchestrator-injected` | Orchestrator after splice | After the orchestrator inserts the rendered block into the spawn prompt — records `hook_record_ts`, `count_injected`, `subagent_type`, `task_id`. Pairs with the matching `logged` record |

Mismatch (a `logged` record without a paired `orchestrator-injected` record for the same `subagent_type` + `task_id` in the same session) is the Path-B disclosure surface — surfaced post-hoc by `/forensics`.

#### Environment variables

| Variable | Default | Effect |
|---|---|---|
| `CLAUDE_INSTINCT_MIN_CONFIDENCE` | `0.4` | Confidence floor; instincts below are rejected. Invalid values fall back to default with a stderr warning. |
| `CLAUDE_INSTINCT_TOP_N` | `5` | Maximum bullets in the rendered block. `0` → empty block; negative or invalid → default. |
| `CLAUDE_INSTINCTS_DIR` | unset | Test-only override of the learning base directory. |
| `CLAUDE_AGENTS_DIR` | unset | Test-only override of the agents directory used by `agent_instinct_categories_loader`. |
| `CLAUDE_DISABLE_INSTINCT_INJECTION` | unset | Set to `1` to fast-exit the hook (per-session escape hatch). |
| `CLAUDE_HOOK_PROFILE` | `standard` | When set to `minimal`, the hook fast-exits — matches the suppression pattern of the four sibling Path-B hooks. |

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

## 5. Learning DB Hygiene

Old observations accumulate without bound. The GC hook keeps the learning DB lean
by archiving past-retention entries and periodically VACUUMing the SQLite index.

### Trigger
`hooks/learning-gc.sh` runs on every SessionStart. It is **idempotent** — state
is tracked in `learning/{project-hash}/.gc-state.json`; GC only fires when at
least 30 days have elapsed since the last run.

### Retention
Controlled by `CLAUDE_LEARNING_RETENTION_DAYS` (default **90 days**). Observations
older than this threshold are moved out of `observations.jsonl` and into
`learning/{project-hash}/archive/observations-YYYY-MM.jsonl.gz` (one file per
calendar month, gzip-appended). The JSONL files remain the canonical source of
truth; archived entries are preserved, not deleted.

**Legacy format note**: observations.jsonl files written before the compact-JSONL
writer (`observation-capture.sh` via `jq -c`) may use pretty-printed multi-line JSON.
The GC parser reads line-by-line; multi-line records are treated as unparseable and
kept in place (not archived). This is intentional — no data loss. To archive
legacy files, convert first with `jq -c . observations.jsonl > compact.jsonl && mv compact.jsonl observations.jsonl`.

### VACUUM
After archiving, `memory.sqlite` is VACUUMed via the `sqlite3` CLI to reclaim
freed pages. Skipped silently if `sqlite3` is not installed or the DB doesn't exist.

### Escape hatch
Set `CLAUDE_DISABLE_LEARNING_GC=1` to suppress the hook entirely (useful for
debugging or bulk-import sessions). The hook never blocks session start — all
errors are logged to stderr and the hook exits 0.

### Archive exclusion
- `/learn` (Step 2a) reads `observations.jsonl` only — not `archive/`.
- `/reindex-memory` ingest globs `learning/*/observations.jsonl` — not `archive/`.
- FTS5 index rebuilds therefore reflect current data; archived entries fall out of
  the search index when they are moved. This is intentional: recall is optimised for
  recent context, not historical breadth.

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

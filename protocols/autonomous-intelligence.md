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

Created by the orchestrator at pipeline start (alongside the pipeline state file). Cleaned up via `find pipeline-state/{task-id} -type f -delete && find pipeline-state/{task-id} -depth -type d -empty -delete` after completion — `rm -rf` on directories is sandbox-denied even on orchestrator-writable paths; see `skills/pipeline/SKILL.md` Step 7d for the canonical snippet. During the DUAL_PATH soak (see `rules/pipeline-protocol.md` § Structured Pipeline State), the legacy form `pipeline-state/{task-id}-scratchpad/` is still tolerated by readers; new pipelines write to the new layout only.

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

**Injection rules** (category × spawn target — see `orchestrator/agent-orchestration.md` § Pipeline Scratchpad Injection for the canonical matrix):
- `warning` → forwarded to ALL subsequent phases (every spawn after the writer)
- `fragility` → forwarded to ALL subsequent phases
- `discovery` → forwarded to the next immediate phase only, then dropped
- `pattern` → forwarded to the same role on subsequent phases only
- `decision` → forwarded to reviewers and Final Gate roles only
- Skip findings from the same role re-spawned within the same phase (they already know)
- If the filtered set is empty, skip the section silently — no header, no placeholder

The `scratchpad-bytes.sh` PreToolUse hook records the post-filter byte count per spawn to `metrics/{session-id}/scratchpad-bytes.jsonl` so regressions in filter behaviour or unexpected bloat are catchable in forensics.

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

When injecting session memory into agent prompts, the orchestrator selects sub-files by **filename** (not by section header inside one file). The role × sub-file mapping is encoded as the SOURCE OF TRUTH in `hooks/_lib/session_memory_role_resolver.py` — `resolve_subfiles_for_role(role) -> list[str]`. The table below mirrors that module; both directions are pinned by `tests/test_session_memory_role_resolver.py`:

| Agent Role | Sub-files Injected (in order) |
|---|---|
| `architect` | `codebase-map.md` *(generated artifact, see § Codebase-Map Sub-file & Soak)*, `patterns.md`, `fragility.md` |
| `software-engineer` | `build-test.md`, `patterns.md`, `fragility.md` |
| `frontend-engineer` | `build-test.md`, `patterns.md`, `fragility.md` |
| `database-engineer` | `build-test.md`, `patterns.md`, `fragility.md` |
| `infrastructure-engineer` | `build-test.md`, `fragility.md` |
| `qa-engineer` | `build-test.md`, `fragility.md` |
| `code-reviewer` | `patterns.md`, `fragility.md` |
| `security-engineer` | `patterns.md`, `fragility.md` |
| `product-reviewer` | (none — product UX content not in engineering memory) |
| `patch-critic` | `fragility.md` |
| `session-memory-updater` | (writes only, no injection) |
| **(any role)** | **`active-work.md` is NEVER injected** |

Sections are concatenated under `## Session Context (engineering notes for this project)`. Each sub-file is preceded by a `### {sub-file}` heading inside the block.

**Empty-body skip rule.** When a sub-file's body (after stripping the `# `-header line, the `_…_` italic-description line, and blank lines) is < 50 chars, the orchestrator omits that sub-file from the rendered block. Helper: `should_inject_subfile(text)` in the resolver module. Fresh projects with all-empty templates inject nothing — same observable behaviour as today's "skip injection if no real content".

**`active-work.md` is orchestrator-only.** It carries current pipeline phase, task-id, branch, and immediate next steps — operational state owned by the orchestrator, not engineering knowledge. It is never read by the injection path; the resolver has no entry point that resolves to it. The orchestrator reads/writes it directly via `session_store_get|put $hash active-work` for its own state tracking.

### Sub-file Layout & Soak

Session memory is stored as a 5-file directory shape per project hash (the C3 split) instead of one monolithic `notes.md`:

```
session-memory/{project-hash}/
  codebase-map.md   # Key dirs, files, entry points
  build-test.md     # Build / test commands, env quirks
  patterns.md       # Patterns, conventions, discoveries, agent effectiveness
  fragility.md      # Critical paths, timing sensitivities, fragile areas
  active-work.md    # Orchestrator-only — never injected
```

Templates seeded from `session-memory/config/templates/{sub-file}.md`. The legacy single-file is migrated by `scripts/migrate-session-memory-split.sh` (idempotent, non-destructive — renames the legacy file to its `.legacy` sibling, supports `--dry-run`). The migration script refuses to operate on symlink targets that resolve outside `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/session-memory/` and archives any pre-existing `.legacy` artifact to `.legacy.{unix_ts}` before writing a fresh one.

**30-day DUAL_PATH soak.** Writers emit only the new layout; readers tolerate both forms via `session_memory_read_split` in `hooks/_lib/session-memory-read-split.sh`. The helper returns the new-layout file when present, falling back to the matching canonical section of the legacy single-file otherwise; each fallback hit appends a forensic JSONL line at `metrics/{session-id}/session-store-mirror.jsonl` with `source: "session-memory-read-fallback"`. The soak ends 30 days after merge, gated by the placeholder `pipeline-state/wave2a-c3-soak-end/pipeline.md` (frontmatter `not_before` carries the calendar anchor; SessionStart's active-pipeline scan surfaces it once the date passes). The follow-up cleanup pipeline removes the reader-fallback code path and any remaining legacy artifacts.

**Updater dispatch.** `session-memory-updater` accepts `targetFile` + `targetSection` inputs and writes exactly one sub-file per spawn. The orchestrator dispatches N parallel updaters (one per affected sub-file, max N=4; `active-work.md` is updated directly by the orchestrator without an updater spawn) — see `orchestrator/agent-orchestration.md` § Session Memory Update for the canonical bash wrap.

### Codebase-Map Sub-file & Soak

`codebase-map.md` is the **only generated artifact** in the sub-file layout. The harness regenerates it from a tree-sitter symbol graph + personalised PageRank (the auto-codebase-map feature) on every SessionStart and whenever the Stop-poll hook detects that `main` has advanced. The on-disk file at `~/.claude/db/codebase-map/{project-hash}/codebase-map.md` is generator-owned; the four other sub-files (`build-test.md`, `patterns.md`, `fragility.md`, `active-work.md`) remain hand-curated.

**Writers MUST NOT include `codebase-map.md` in updater dispatch.** `session-memory-updater` is the only writer-class agent in the harness; the dispatch path (`hooks/_lib/session-memory-updater-dispatch.sh`) refuses any spawn whose `targetFile` is `codebase-map.md` and exits 1 with a `{"error":"generated_artifact_misroute","action":"spawn_refused"}` JSONL marker on stderr. **The refusal is permanent architecture, not soak scaffolding** — generator-owned artifacts are off-limits to the writer-class regardless of soak state. Re-introducing the writer path on any future regression would corrupt the generator's deterministic byte-equal contract.

**30-day DUAL_PATH soak.** During the migration window, readers (`hooks/_lib/session-memory-read-split.sh`) prefer the generator output and fall back to any operator-authored manual `codebase-map.md` only when the generator file is absent (rebuild failed, fresh install pre-rebuild). When BOTH files are present and content differs, the reader returns the generator output AND emits one JSONL line at `metrics/{session-id}/codebase-map-divergence.jsonl` with `source: "codebase-map-divergence"` and a content-hash pair (no full content — privacy + size). The window mirrors the `CLAUDE_LEARNING_RETENTION_DAYS` floor and the C3 soak precedent above.

**Soak end (4-item cleanup).** The placeholder pipeline at `pipeline-state/auto-codebase-map-soak-end/pipeline.md` carries the `not_before:` calendar anchor (merge_date + 30 days). When the date passes, the cleanup pipeline executes exactly **4 cleanup items**:

1. Remove the reader-fallback branch from `session-memory-read-split.sh`.
2. Sweep operator-authored manual `codebase-map.md` files into `.legacy` siblings (per the migration-script preserve-do-not-delete precedent).
3. Assert no `codebase-map-divergence.jsonl` hits in the last 7 days as a gate condition.
4. Update this section to mark the codebase-map soak as complete.

The updater-dispatch refusal is **deliberately not on the cleanup list** — see the permanent-architecture clause above.

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
    "build": {
      "verdict": "BUILD_COMPLETE",
      "rounds": 1,
      "agents": [
        {"role": "software-engineer", "model": "claude-sonnet-4-6"}
      ]
    },
    "review": {"verdict": "APPROVE", "rounds": 2, "findings": 3},
    "verify": {"verdict": "VERIFIED", "tiers_passed": 3, "mutation_score": 0.78},
    "test": {"verdict": "COVERED", "coverage": 92},
    "accept": {"verdict": "APPROVED", "conditions": 0},
    "patch_critic": {
      "verdict": "PATCH_APPROVED",
      "rounds": 1,
      "mode": "multi-persona",
      "persona_rejections": []
    },
    "pdr_rtv": {
      "verdict": "PDR_WINNER_SELECTED",
      "n_candidates_iter0": 4,
      "n_candidates_iter1": 4,
      "tournament_rounds": 3,
      "winner_slug": "iter1-c",
      "cost_estimate_usd": 1.8721
    }
  },
  "scratchpad_findings": ["list of category:summary from scratchpad"],
  "rework": false,
  "duration_phases": 6,
  "complexity_budget": 9,
  "cost_estimate_usd": 0.4231
}
```

#### Field reference

| Field | Type | Source |
|---|---|---|
| `cost_estimate_usd` | number (USD float, dollars) | computed via `hooks/_lib/cost_estimator.py` from `metrics/{session-id}/tool-timings.jsonl` records for this pipeline (joined by `task_id`). The producer calls `estimate_cost_usd_per_pipeline(timings_path)` and reads the value keyed by the current `task_id`; the result is a sum across every tool call attributed to the pipeline. |
| `phases.build.agents` | array of `{role: string, model: string}` objects | one entry per build agent spawned for this pipeline (single-slice → length 1; multi-slice → length N). `role` matches the agent frontmatter `name:` field (`software-engineer`, `frontend-engineer`, etc.); `model` is the resolved executor (`claude-opus-4-7`, `claude-sonnet-4-6`, …). This is the canonical primary-key source for `(agent_role, task-class)` aggregation in `/learn` Step 7c — the prior integer-count form was deprecated when per-(role, task-class) cost-quality correlation was introduced in B12.2. |
| `phases.verify.mutation_score` | number in `[0.0, 1.0]`, OR absent | mutation kill-rate on changed lines, captured by `/verify` Tier 3. Absent when the verify phase did not run a mutation pass (e.g. docs-only changes that skipped Tier 3 with documented rationale per `protocols/engineering-invariants.md` § Proof of Correctness). The Iron Law (`rules/core.md` § 1) requires ≥0.70 on changed lines for any AC-bearing slice; observation readers MUST treat absence as "unknown", NOT as `0.0`. |
| `phases.patch_critic` | object `{verdict, rounds, mode, persona_rejections?, evidence_mode?}`, OR absent | written by Reflect step from the Final Gate patch-critic verdict. `verdict` is `PATCH_APPROVED` or `PATCH_REJECTED`. `rounds` is the count of patch-critique cycles in this pipeline (initial + any re-critiques after fix-engineer rework). `mode` is `single-critic` or `multi-persona`. `persona_rejections` is an array of `{persona, dimension, severity}` (MEDIUM-or-greater only) — present in `multi-persona` mode regardless of verdict (empty array on PATCH_APPROVED). Single-critic mode omits `persona_rejections`. `evidence_mode` is OPTIONAL with values `"diff-only" \| "diff+execution"` — written when the optional execution-evidence path described in `orchestrator/parallel-dispatch-details.md` § Multi-Persona Patch Critic Dispatch / Execution Evidence is active. `"diff+execution"` indicates all three steps (env-var probe, generator, sandboxed run) completed successfully and the persona prompts received an `## Execution Evidence` block; `"diff-only"` indicates the path was deliberately not taken (flag off OR any silent skip). Readers MUST tolerate absence as a legacy / pre-exec-layer record — absence and `"diff-only"` are forensically distinct (legacy vs deliberate diff-only). C8 anti-pattern mining gates on `rounds >= 2` (see § Scratchpad → Instinct Promotion); `evidence_mode` is informational only and does NOT participate in the mining gate. When tagging mined anti-pattern instincts derived from `phases.patch_critic` rounds, `/learn` SHOULD set the instinct's `roles:` to the persona category (`patch-critic-correctness`, `patch-critic-regression`, or `patch-critic-scope`) drawn from `persona_rejections[].persona`, so future patch-critic spawns receive specialty-tuned learned patterns. |
| `phases.pdr_rtv` | object `{verdict, n_candidates_iter0, n_candidates_iter1, tournament_rounds, winner_slug, cost_estimate_usd, fallback_reason?}`, OR absent | written by Reflect step from the Build-phase PDR-RTV dispatch (when `/intake` set `pdr_rtv: true` and the variant ran). `verdict` is `PDR_WINNER_SELECTED` or `PDR_NO_CONSENSUS`. `n_candidates_iter0` and `n_candidates_iter1` are the count of green-build rollouts at each iteration (default N=4 each). `tournament_rounds` is the count of pairwise comparison rounds (e.g. log2(8)=3 for the default N=4 × T=2). `winner_slug` is the slug of the rollout that won the tournament (empty / null on `PDR_NO_CONSENSUS`). `cost_estimate_usd` is the variant's marginal cost (8 sequential rollouts + N-1 tournament comparisons, ≈4-5× standard Build). `fallback_reason` is OPTIONAL — present iff `verdict == PDR_NO_CONSENSUS`, with values `"worktree-cap-exceeded"` \| `"insufficient-green-builds"` \| `"all-finalists-rejected"` \| `"missing-meta"` \| `null`. The same enum value is mirrored in `pipeline-state/{task-id}/pipeline.md` § Re-routes when a fallback occurs, so forensics and `/eval-model-effectiveness` can join the two surfaces. Readers MUST tolerate absence per existing schema-compatibility rules — absence means the pipeline did not run a PDR-RTV dispatch (the default for non-critical, sub-budget-9 work), NOT a synthetic `PDR_WINNER_SELECTED` + 0 cost. Absence and explicit `null` are forensically distinct (variant-not-run vs no-fallback-fired). |
| `phases.build.wave_count` | `int`, OR absent | written by the v2 wave dispatcher at Reflect time (see `orchestrator/parallel-dispatch-details.md` § Multi-Slice DAG Mode (schema_version: 2) / Forensic Fields). Counts the number of waves the knapsack-packed dispatcher ran for this Build phase. Present ONLY on schema_version: 2 pipelines — v1 plans use the legacy flat multi-slice path which does not emit wave metrics. Readers MUST tolerate absence (treat as "v1 pipeline / wave metrics not captured", NOT as `0`); aggregations that join on this field must filter missing rows out rather than coercing them to zero. |
| `phases.build.wave_widths` | `list[int]`, OR absent | written by the v2 wave dispatcher at Reflect time alongside `wave_count`. Per-wave selected-slice counts after knapsack packing — `len(wave_widths) == wave_count`. Per-wave width is bounded above by `min(CLAUDE_BUILD_WAVE_MAX_PARALLEL, ready_set_size)`. Same absence-tolerance contract as `wave_count`: present ONLY on schema_version: 2 pipelines; readers MUST treat absence as unknown, not as `[]`. |
| `phases.sandbox_verify` | object `{verdict, rounds, cost_estimate_usd, mode?, divergence_count?, skip_reason?, diverging_tests?}`, OR absent | written by Reflect step from the Build-phase Step 5b `/sandbox-verify` gate (added in the sandbox-verify epic, Stories 1-4). `verdict` is one of `SANDBOX_VERIFIED`, `SANDBOX_FAILED`, `SANDBOX_SKIPPED`. `rounds` is the count of sandbox-verify cycles in this pipeline (initial + any re-runs after fix-engineer rework; shares the combined 2-round budget with code-review per `skills/build-implementation/SKILL.md` Step 5b). `cost_estimate_usd` is the sandbox spend captured from `metrics/{session-id}/sandbox-verify-cost.jsonl` teardown events (may be `0.0` or absent when cost data is unavailable). `mode` is OPTIONAL with values like `"diff-only" \| "exec"` reserved for forward-compatibility with future verifier modes. `divergence_count` is present iff `verdict == SANDBOX_FAILED` — the count of test rows where worktree and sandbox disagreed. `skip_reason` is present iff `verdict == SANDBOX_SKIPPED`, with enum values `"no-e2b-token" \| "no-testable-changes" \| "env-hatch" \| "e2b-unavailable" \| "cost-exceeded"`. `diverging_tests` is OPTIONAL and present iff `verdict == SANDBOX_FAILED` — a `list[str]` of test names from `pipeline-state/{task-id}/build.md` § Sandbox Verify (bounded at 20 entries to keep observation lines under any downstream size cap; truncation is logged in the build agent's scratchpad when applied). Readers (`/learn`, `/forensics`, `/eval-model-effectiveness`, `/cost-report`) MUST tolerate absence per existing schema-compatibility rules — absence means the pipeline did not run a `/sandbox-verify` Build-phase gate (legacy pipeline or build-only docs change), NOT a synthetic `SANDBOX_VERIFIED` + 0 cost. Mining via `learn_sandbox_fragility_mining.mine_sandbox_fragility` (`/learn` Step 3) recurrence-3-gates on `diverging_tests` to emit `fragility` instincts at confidence 0.5 with roles `[software-engineer, sandbox-verify-engineer]`. |

The cost estimator is the single source of truth for token-to-USD conversion (see `PRICING_PER_MILLION` in `hooks/_lib/cost_estimator.py`). Unknown models contribute `0.0` and emit a deduplicated stderr warning — they do NOT raise, so a partial-pricing record always produces a numeric estimate.

**Backward compatibility:** readers (`/learn`, `/forensics`, `/eval-model-effectiveness`) MUST tolerate absence of `cost_estimate_usd` in legacy records written before this field was introduced. Treat absence as "unknown cost", NOT as `0.0` — a missing field is not the same as a free pipeline. Aggregations that need cost data should filter out records where the field is missing rather than coercing them to zero (which would skew downward averages).

The same tolerance applies to `phases.patch_critic`: readers MUST treat absence as "patch-critic data not captured for this pipeline" — NOT as a synthetic `PATCH_APPROVED` + 0 rounds. Aggregations that gate on `phases.patch_critic.rounds` (e.g., the C8 mining gate in § Scratchpad → Instinct Promotion) MUST filter out records where the field is missing rather than coercing them to zero.

The same tolerance applies to `phases.sandbox_verify`: readers MUST treat absence as "sandbox-verify data not captured for this pipeline" — NOT as a synthetic `SANDBOX_VERIFIED` + 0 cost. Consumers use `hooks/_lib/sandbox_verify_observation.is_present` as the canonical filter predicate. Mining helpers (`learn_sandbox_fragility_mining.mine_sandbox_fragility`) iterate `is_present`-filtered records ONLY; legacy records without the block are skipped, never contributing 0 to any aggregate.

**Implementation status (2026-05-09):** the producer hook (`hooks/observation-capture.sh` is per-tool only; the per-pipeline writer lives in `skills/pipeline/SKILL.md` Step 7b-bis (regular pipeline — added 2026-05-09) and `skills/batch-pipeline/SKILL.md` Step 6 (batch pipeline) — see those skill files for the exact JSON template + sandbox-safe append snippet) emits `cost_estimate_usd` only when `tool-timings.jsonl` contains the input data required by `cost_estimator.py` (`model` + `input_tokens` + `output_tokens` + optional cache-token fields). As of this slice, `tool-timings.jsonl` lacks those fields — the current shape is `{ts, tool, duration_ms, success, agent_role?, task_id?}` per `hooks/_lib/tool-timing-emit.py`. Until the upstream emitter is updated to capture model + token counts (see B12.3 follow-up for the producer-side wiring), `cost_estimate_usd` will be omitted from observation records and downstream consumers will see the field as absent. The field is documented here so the schema is stable when the producer lands; readers must already tolerate absence today.

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
- ≥3 pipelines in the same project where a Sonnet executor required ≥2 review rounds for the same role → set `prefer_opus: true` on the relevant instinct so subsequent spawns escalate to Opus (deferred — see § Instinct Injection)
- Same scratchpad finding recurring across 3+ pipelines that ALSO carry `(phases.review.rounds >= 2 OR phases.patch_critic.rounds >= 2)` → emit an **anti-pattern** instinct (`category: anti-pattern`) at confidence `min(0.85, floor + 0.05 * (N - 3))` where `N` is the distinct pipeline count and `floor` is resolved from a domain-weighted map: `{workflow: 0.5, testing: 0.6, code-style: 0.6, architecture: 0.7, security: 0.7}` (default `0.5` for unknown domains). The cap (0.85) is uniform across domains — higher-floor domains reach it with fewer recurrences (architecture/security cap at N=6, testing/code-style at N=8, workflow at N=10). Mining is iron-law-gated on `rounds >= 2` because fix-engineer is dispatched on every CHANGES_REQUESTED AND on every PATCH_REJECTED (per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule), so `rounds >= 2` on either phase is a perfect proxy for "fix-engineer ran". When mining via `phases.patch_critic.rounds`, `/learn` SHOULD tag the resulting anti-pattern instinct's `roles:` with the persona category (`patch-critic-correctness`, `patch-critic-regression`, or `patch-critic-scope`) drawn from `persona_rejections[].persona` so future spawns receive specialty-tuned learning. Legacy observations missing the rounds field on either phase are SKIPPED for that gate clause (the OR still fires if the OTHER clause clears), NEVER coerced to 0. Anti-pattern instincts surface in agent prompts with the `AVOID:` prefix and trigger the +0.1 floor boost described in § Instinct Injection. Anti-patterns are excluded from the Step 7b auto-scaffold scan — they are guidance, not promotable verdicts.

### Instinct Injection (Path-B advisory)

The PreAgent hook `hooks/instinct-injector.sh` (registered on the `Agent` matcher at PreToolUse position 6, between `pre-agent-allowlist.sh` and `depth-guard.sh`) computes which instincts apply to each spawn target and records the resolution to `metrics/{session-id}/instinct-injections.jsonl` for forensic visibility. The hook is **advisory/log-only today**: the Agent tool input schema does not yet expose `modified_tool_input`, so the hook cannot patch the spawn prompt. Actual `## Learned Patterns` injection into the prompt body is performed by the orchestrator at spawn time (see `orchestrator/agent-orchestration.md` § Spawn Procedure / § Instinct Injection). When `modified_tool_input` lands, only `hooks/instinct-injector.sh` flips behaviour — resolver, loader, agent frontmatter, and the orchestrator-caller contract are unchanged.

#### Selection algorithm

1. **Load instincts** from `learning/{project-hash}/instincts/*.md` (project-scoped) and `learning/instincts/*.md` (global), via `hooks/_lib/instinct_loader.py`. Per-file failures are skipped with a `source: "load-warning"` JSONL record — the loader never raises.
2. **Filter by role**: keep instincts whose `roles:` set intersects the spawning agent's `instinct_categories:` set (per-agent frontmatter, loaded by `hooks/_lib/agent_instinct_categories_loader.py`).
3. **Filter by confidence floor**: drop any instinct with `confidence < CLAUDE_INSTINCT_MIN_CONFIDENCE` (default `0.4`).
4. **Dedup by `id`**: when the same `id` appears in both project and global directories, the project entry wins (project beats global).
5. **Sort and cap**: sort by `confidence` DESC, secondary sort by `id` ASC for stability, then keep the top `CLAUDE_INSTINCT_TOP_N` (default `5`; `0` produces an empty block).

The actionable summary in each rendered bullet comes from the `## Pattern` body of the instinct file (first non-empty line, truncated at 200 chars), NOT from a frontmatter field.

#### Anti-pattern floor boost (+0.1)

When at least one **anti-pattern** instinct (`category: anti-pattern`) survives the base role+confidence filter, the resolver re-filters non-anti-pattern instincts at `floor + 0.1`. The boost prevents weak positive guidance from crowding out the anti-pattern signal — a 0.45-confidence positive evaporates when an anti-pattern fires, while a 0.65-confidence positive survives. Anti-patterns are explicitly preserved through the boosted-floor pass (they would otherwise self-evict at boundary cases like a 0.51-confidence anti-pattern against a 0.5 base floor); they ship at confidence ≥ 0.5 by construction so the boost is rarely consequential for them. Anti-pattern bullets render with the `AVOID:` prefix added AFTER `_truncate`, so they may be ~210 visible chars (the prefix sits OUTSIDE the 200-char truncation budget).

#### Per-agent `instinct_categories:` contract

Every file in `agents/*.md` declares an `instinct_categories:` YAML list of role-name tokens. An instinct matches an agent IFF `set(instinct.roles) ∩ set(agent.expanded_instinct_categories) != ∅`, where the expanded set is the union of the agent's own flat declaration and every ancestor's flat declaration walked transitively via the optional `parent:` field (see Parent inheritance below). The full per-role flat mapping lives in `tests/test_agent_instinct_categories.py` as a snapshot — any frontmatter drift fails CI. The list MUST be a YAML list (not a comma-separated string); regression test `tests/test_learn_roles_enforcement.py` locks the contract in both directions.

##### Parent inheritance

An agent may declare an optional `parent: <role>` field pointing to another agent in `agents/*.md`. The instinct-injection caller resolves the agent's effective categories by walking the parent chain transitively: own flat categories ∪ parent's flat ∪ parent's parent's flat ∪ … until `parent:` is absent (root) or the walk would revisit a name already in the visited-set (cycle).

Resolution lives in `hooks/_lib/agent_parent_chain.py`:

- `resolve_parent_chain(subagent_type)` — returns the ordered ancestor list, terminating at root or cycle. Visited-set guards against `A→B→A` loops.
- `load_expanded_instinct_categories(subagent_type)` — returns the sorted union of own + ancestor flat categories. The production caller `hooks/_lib/resolve-instincts.py` invokes this; the orchestrator's canonical Python snippet in `agent-orchestration.md` § Instinct Injection mirrors the call.

Missing-parent handling: when `parent: <name>` resolves to a path that does not exist (e.g. `<name>.md` was renamed without updating descendants), the resolver emits a one-line warning to **stderr** AND appends a JSONL forensic record to `metrics/{session-id}/parent-chain-warnings.jsonl` (`{source: "missing-parent", agent: <child>, missing: <name>}`). The chain returns the partial accumulation up to the missing link; the resolver does NOT raise. Operators see degradation in their terminal output (stderr) without the pipeline crashing.

Today only `frontend-engineer` declares a `parent:` (→ `software-engineer`). The mechanism is one-deep in the current agent set; the transitive walk and cycle protection are forward-looking for deeper chains (e.g. a future `security-architect.parent → architect`).

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

#### Executor Override (prefer_opus)

Wave 5/B6.3 introduces an OPTIONAL `prefer_opus: true` field in the instinct YAML frontmatter. When an instinct carrying the flag fires for a (role, project) pair — i.e. the instinct's `roles:` set intersects the spawning agent's expanded `instinct_categories` AND its `confidence` clears the floor — the orchestrator's executor resolver overrides the spawn's executor to `claude-opus-4-7`, regardless of the agent's frontmatter `executor:` value.

Trigger condition (set by `/learn`): ≥3 pipelines in the same project where a Sonnet executor required ≥2 review rounds for the same role. The flag is data-driven escalation — the system learns when a given (role, project) routinely needs deeper reasoning and starts routing it to Opus automatically.

`prefer_opus` lives at instinct file scope alongside `id`, `confidence`, `roles`, and `domain`. Validation: when present, must be a YAML bool. Non-bool values (e.g. `prefer_opus: "yes"`) are rejected by `instinct_loader_helpers.validate` with the warning code `non-bool-prefer-opus` and coerced to `False` by `normalize`. Absent: treated as `False`. The normalised dict surface is seven keys: `id`, `confidence`, `roles`, `domain`, `scope`, `pattern_summary`, `prefer_opus`.

**Not yet implemented — `/learn` writer and orchestrator reader deferred to the next learning slice. Manually-authored instincts may set the flag, but the orchestrator does not yet consume it.** Slice B6.3 ships the parser/validator/normalizer paths and the contract docs only. The reader (orchestrator-side `executor_resolver.resolve_executor` extension that loads instincts and short-circuits to Opus on a `prefer_opus: true` match) is the next layer up.

## 4. Prompt Tracing (Opt-In)

Debugging aid for agent failures: capture the exact rendered prompt the orchestrator sent to a spawn — skills, instincts, session memory, scratchpad, agent memory, all already composed into `tool_input.prompt` by the orchestrator.

### Enabling

Tracing is **off by default** (`CLAUDE_ENABLE_TRACE=0` in `settings.json` env block). The hook's first line fast-exits when disabled — zero overhead in the default state.

To enable for the current session, invoke `/debug-trace on`. To disable, `/debug-trace off`. The toggle is per-session; the durable default (off) lives in `settings.json` and survives session boundaries. See `skills/debug-trace/SKILL.md` for the full skill contract.

Direct env-var override (`CLAUDE_ENABLE_TRACE=1`) still works for callers who want to enable tracing outside a Claude Code session — the skill is a convenience, not a gate.

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
1. Create scratchpad directory: `mkdir -p pipeline-state/{task-id}/scratchpad/`
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

---
name: "intake"
description: "Entry point for all user requests. Classifies work type (feature, refactor, bug, spike, question), estimates complexity, determines pipeline entry point, and invokes /harness:pipeline. Use when receiving any new task from the user."
argument-hint: "Feature, bug, or task description"
---

# Task Intake

## What This Skill Does

Entry point for all user work requests. Classifies the work, estimates complexity, and routes to the appropriate pipeline or skill.

## Process

### Step 1: Classify the Work

| Signal | Classification | Entry Point |
|--------|---------------|-------------|
| "Add feature", "Implement", new AC | **Feature** | `/harness:pipeline` → `/harness:build-implementation` |
| "Refactor", "Decompose", "Extract", shape violation | **Refactor** | `/harness:pipeline` → `/harness:refactor` |
| "Bug", "Fix", "Broken", "Error", failing test | **Bug Fix** | `/harness:pipeline` → `/harness:bug-fix` |
| "Spike", "Investigate", "Evaluate", "Research" | **Tech Spike** | `/harness:tech-spike` (no pipeline) |
| "Epic", "Feature set", multiple stories | **Epic** | `/harness:epic-breakdown` → `/harness:pipeline` per story |
| Question, "How does", "Explain", "What is" | **Question** | Answer directly (no pipeline) |
| "Set up", new repo, no CLAUDE.md | **Project Setup** | `/harness:project-setup` → Plan phase |
| "Build me", "Create a", "new app", "from scratch", empty directory, no package.json/Gemfile/go.mod | **Greenfield** | `/harness:greenfield-scaffold` → `/harness:epic-breakdown` → `/harness:pipeline` per story |
| "API", "endpoint", "resource" (new API) | **Feature + Scaffold** | `/harness:pipeline` → `/harness:api-scaffold` → `/harness:build-implementation` |
| "Migration", "schema", "add column" | **Feature + Scaffold** | `/harness:pipeline` → `/harness:db-migration` → `/harness:build-implementation` |
| "Docker", "CI/CD", "deploy", "infra" | **Infrastructure** | `/harness:pipeline` → `/harness:infra-scaffold` |
| "Extract", "split out", "carve out", "separate", "move into its own" (no FF named) | **Module Extraction** | `/harness:pipeline` → `/harness:module-extraction` (same repo) |
| "Extract to a service", "new repo", "own service", "separate deploy", or any FF named explicitly | **Service Extraction** | `/harness:pipeline` → `/service-extraction` (multi-repo) |
| "Logging", "monitoring", "observability" | **Infrastructure** | `/harness:pipeline` → `/harness:observability-setup` |
| Multiple repos referenced, "API + frontend", cross-service | **Multi-Repo Feature** | `/harness:pipeline` (multi-repo mode) |
| "New service" + FF named, "new repo" + FF named, scaffold-service request | **Service Scaffold** | `/harness:pipeline` → `/microservices-scaffold` (multi-repo) |
| "New service" with no FF named | **Ambiguous — probe** | Intake runs the forcing-function decision tree below |

### Step 1b — Forcing-Function Decision Tree (always runs when Step 1 routes to Service Extraction / Scaffold — exits at step 1 if FF is explicit)

1. **Explicit FF in the request text?** (keyword scan: "for compliance", "for independent scaling", "blast radius", "team ownership", "regulatory", "HIPAA", "PCI", "GDPR", "data residency", "polyglot")
   - Yes → route to `/service-extraction` or `/microservices-scaffold`.
   - No → continue.
2. **Project already multi-repo?**
   - Project CLAUDE.md has a `## Service Context` section → route to service.
   - No → continue.
3. **Default**: route to `/harness:module-extraction`. Log the decision to `pipeline-state/{task-id}/intake.md` with rationale: "No FF detected; no existing Service Context. Defaulting to module extraction."

**No user prompt.** Plan Validation challengers receive the routing rationale and can flip it if wrong.

### Step 1.5: Fingerprint (MANDATORY — runs before Complexity Budget)

Fingerprint the work into one of seven tiers (T0..T6) per `protocols/work-class-routing.md`. Tier determines dispatch shape; Complexity Budget (Step 2) shapes intra-tier dispatch. Detector cascade ships **Phase 1 + Phase 2 + fallthrough** in this pipeline. **Phase 3 deferred** — see § Phase 3 Status in `pipeline-state/integrate-work-class-routing/plan.md` for the rationale.

#### Phase 1 — Rule-based pass (no model call, $0)

Run the regex/glob detectors from `protocols/work-class-routing.md` § Fingerprint Phase 1 against predicted file paths and user prompt:

- `T1_doc_only` — ALL paths match `*.md` / `*.txt` / `*.rst` / `docs/*` / `README*`; no code/config/shell-script body change
- `T2_config_only` — ALL paths match `settings.json` / `*.yml` / `*.yaml` / `*.toml` / `agents/*.md` frontmatter-only
- `T3_mechanical_sweep` — uniform transformation across at least 3 files (rename / replace / lint-fix / version bump / import sort)

If a detector resolves with high confidence, emit that tier as `tier_emitted` and `tier_initial`, set `detector_phase: rules`, `detector_confidence: high`.

#### Phase 2 — Safety override (always runs, never downshifts)

ANY of these force T4+ regardless of Phase 1 verdict (set `safety_override_fired: true`):

- Predicted scope includes `hooks/*.sh` body changes (not entry-syntax-only)
- Predicted scope touches `rules/core.md`, `protocols/atdd-procedure.md`, or `protocols/verdict-catalog.md` — **any touch upshifts to T6** (conservative — Iron-Law-surface floor per plan § HIGH-1)
- Predicted scope includes any test file
- User prompt contains `auth` / `payment` / `token` / `secret` / `crypto` / `password` / `session` in change-target context
- Predicted scope includes `auth/*` / `secrets/*` / `*crypto*` / `*.env`

If safety override fires, set `tier_emitted: T6` (or T4 minimum for non-Iron-Law-surface safety), `detector_phase: rules`, `detector_confidence: high`.

#### Phase 3 — Haiku tiebreaker (DEFERRED in this pipeline)

When Phase 1 is ambiguous AND Phase 2 did not fire, fall through with `tier_emitted: T4`, `detector_phase: fallthrough`, `detector_confidence: low`, `fingerprint_cost_tokens: 0`. Spec `protocols/work-class-routing.md:89` documents fallthrough-to-T4 as accepted mitigation. **Phase 3 deferred** to a follow-up pipeline.

#### Override discipline

| Token in user prompt | Effect |
|---|---|
| (default) | Auto-detect per Phase 1, then Phase 2, then fallthrough |
| `[force-pipeline]` | Force T4+ regardless of fingerprint (`override_token: "[force-pipeline]"`) |
| `[force-class:Tn]` | Force specific tier (`override_token: "[force-class:Tn]"`) — but Phase 2 safety override still wins on safety-sensitive paths |

#### Status line

Always emit one of:

```
[Intake] Tier: T0 (reason: rules; phase: 1; confidence: high)
[Intake] Tier: T1 (reason: rules; phase: 1; confidence: high)
[Intake] Tier: T6 (reason: rules; phase: 2; confidence: high)
[Intake] Tier: T4 (reason: fallthrough; phase: 1; confidence: low)
```

Reason enum: `rules` | `fallthrough` (Phase 3 `haiku` reserved for follow-up). Phase enum: `1` | `2`. Confidence enum: `high` | `medium` | `low`.

#### Persistence to `pipeline-state/{task-id}/intake.md` frontmatter

Persist the following 12 forensic-schema fields (read by `hooks/intake-fingerprint-audit.sh`):

```yaml
tier_emitted: T0|T1|T2|T3|T4|T5|T6
tier_initial: T0|T1|T2|T3|T4|T5|T6        # Phase 1 raw output (pre-Phase-2 upshift)
detector_phase: rules|fallthrough
detector_confidence: high|medium|low
user_phrasing_signals: []                  # YAML list of matched phrasing tokens
phrasing_honoured: true|false
override_token: "[force-pipeline]"|"[force-class:Tn]"|null
safety_override_fired: true|false
predicted_files: []                        # YAML list of explicit user-named files
fingerprint_cost_tokens: 0                 # Always 0 in this pipeline — Phase 3 deferred
criticality_filtered_by_tier: true|false   # Step 2d post-fingerprint critical filter
task_id: {task-id}
```

The PostToolUse hook `hooks/intake-fingerprint-audit.sh` reads these fields post-hoc and emits one JSONL line per intake to `metrics/{session}/intake-overrides.jsonl`. The 13th key (`timestamp`) is generated by the hook itself.

### Step 2: Complexity Budget (MANDATORY — score before routing)

Score each dimension 1-3 and sum. This is not optional — routing depends on the total.

| Dimension | 1 (Low) | 2 (Medium) | 3 (High) |
|-----------|---------|-----------|----------|
| **Scope** (files to touch) | 1-3 files | 4-10 files | 11+ files |
| **Ambiguity** (requirement clarity) | Fully specified ACs | Interpretation needed | Discovery required |
| **Context Pressure** (codebase knowledge) | Single module | Cross-module | System-wide |
| **Novelty** (precedent exists?) | Pattern to follow | Partial precedent | Greenfield |
| **Coordination** (cross-cutting?) | Isolated | 2-3 concerns | Auth + data + UI + infra |

**Thresholds → routing:**

| Budget | Action | Pipeline Scale |
|--------|--------|---------------|
| 5-6 | Execute directly, no planning needed | Micro/Small |
| 7-8 | Compound — plan first, then build | Small/Medium |
| 9-10 | Compound — plan first, then build | Medium |
| 11-12 | Multi-session — break into sub-tasks | Large |
| 13-15 | **Must decompose** before starting — use `/harness:epic-breakdown` | Epic |

**Output the score explicitly:**
```
[Intake] CB Score: Scope=N, Ambiguity=N, Context=N, Novelty=N, Coordination=N → Total=N
[Intake] Routing: [execute directly / plan first / decompose]
```

### Step 2b: Exploration Gate (MANDATORY when Ambiguity >= 2)

Before routing to a full pipeline, confirm the approach is validated:

1. **Integration point**: "Where does this render / execute / integrate? Does it replace existing behavior, extend it, or live separately?"
2. **Fidelity**: "Should I build a throwaway prototype first, or go straight to production code?" If prototype → route to `/harness:tech-spike`
3. **External data**: "Do I have the real data structure (API response, HTML, schema), or am I guessing?" If guessing → request it before building
4. **Approach validation**: If multiple implementation approaches exist (e.g., injection vs component, server vs client, sync vs async), confirm the approach with the user before committing

Skip this gate only when Ambiguity = 1 (fully specified ACs with no interpretation needed).

**Why:** Building the wrong approach through a full pipeline wastes more effort than asking 2-3 clarifying questions upfront.

#### Discussion Persistence (MANDATORY when this gate fires)

Create `pipeline-state/{task-id}/discussion.md` to persist the exploration discussion:

```markdown
---
task_id: {task-id}
phase: intake
gate: exploration
ambiguity_score: {N}
timestamp: {ISO 8601}
---

## Discussion: {task summary}

### Questions Asked
| # | Question | Category | User Response | Decision |
|---|----------|----------|---------------|----------|
| 1 | {question} | {integration/fidelity/data/approach} | {response} | {decision made} |

### Decisions Summary
- {Decision 1}: {rationale}

### Impact on Implementation
- Approach: {chosen approach from validation}
- Integration point: {where it fits}
- Data assumptions: {confirmed or external data provided}
```

This file feeds into the architect during the Plan phase and survives context compaction.

### Step 2c: Multi-Repo Detection (Automatic)

Check for multi-repo signals BEFORE routing to pipeline:

1. **Manifest exists?** Check `~/.claude/manifests/` for a project matching the current repo
2. **Service Context?** Check project CLAUDE.md for `## Service Context` with upstream/downstream
3. **Request signals?** Does the user's request reference:
   - Multiple repos or services ("API and frontend", "billing service")
   - Service extraction ("extract", "split out", "own repo")
   - Cross-repo changes ("update the contract", "both services")
   - New service creation ("new service", "scaffold a service")

If ANY signal is true:
- Flag `multi_repo: true` in the routing output
- The pipeline will auto-create/read the manifest (see `protocols/multi-repo-protocol.md`)
- No separate command needed — the pipeline handles it

```
[Intake] Multi-repo: yes/no
[Intake] Manifest: {path} / will be created / N/A
```

### Step 2d: Criticality Tag (MANDATORY)

Emit `critical: true` when ANY of these apply to the task (not merely the files it touches):

- **Payment flow**: keywords `payment`, `billing`, `stripe`, `charge`, `subscription`, `checkout`, `invoice`
- **Auth flow**: keywords `auth`, `login`, `session`, `jwt`, `oauth`, `sso`, `password`, `2fa`, `mfa`
- **Security-sensitive**: keywords `permission`, `rbac`, `authorization`, `csrf`, `xss`, `sanitize`, `encrypt`, `secret`, `credential`
- **Cross-repo contract change**: a manifest exists AND the task modifies files matching `*contract*`, `*.proto`, `openapi.*`, or `*schema*`
- **Production-blocking bug**: classification is Bug Fix AND the user text mentions `production`, `prod outage`, `blocking`, `revenue`, `p0`, `p1`, or `incident`

A keyword match alone is not sufficient; the tag reflects the actual scope. If the change only *touches* auth code but is not *about* auth behaviour (e.g. a copy change in an auth screen, a log format tweak), do not tag.

**Tier filter (post-fingerprint)**: when `tier ∈ {T1, T2}` AND `safety_override_fired == false`, the `critical: true` claim from user phrasing or keywords is **rejected** — emit `critical: false` and set `criticality_filtered_by_tier: true` in the frontmatter. Rationale: T1/T2 routes target docs/config edits where a misclassified `critical` flag would burn heavy-pipeline cost on cosmetic work. Safety override (Phase 2) protects against an auth keyword in a T1-shaped change: if it fires, `critical: true` survives unchanged.

Always print one of:

```
[Intake] Criticality: critical
[Intake] Criticality: standard
```

Persist the flag to `pipeline-state/{task-id}/intake.md` frontmatter as `critical: true|false`. `/harness:pipeline` reads this flag to decide whether the Build phase routes to `/harness:best-of-n` or the standard `/harness:build-implementation`.

### Step 2d-bis: Best-of-N + PDR-RTV Tags (MANDATORY)

Derive two Build-phase dispatch flags. Both are persisted to `pipeline-state/{task-id}/intake.md` frontmatter and read by `/harness:pipeline` Step 3 at Build dispatch time. Routing precedence is `pdr_rtv > bestofn > standard` per `protocols/pipeline-protocol.md` § Build Phase Dispatch Variants.

**Tier gate (post-fingerprint)**: both `bestofn` and `pdr_rtv` only fire at **T6**. At T4/T5, force both flags to `false` regardless of derivation — heavy Build variants exist for critical/cross-cutting work, not for standard features or bug fixes. Spec `protocols/work-class-routing.md:193` is the source of truth.

#### Best-of-N Flag

Derive `bestofn`:
`bestofn = (tier == T6 AND budget >= 7 AND critical) OR user_override`

Where `user_override` is true when the user's request contains the literal token `[best-of-n]` (case-insensitive). The override bypasses the tier+budget gate entirely. The tier+budget+critical conjunction is the SSOT — `hooks/_lib/bestofn_gate.py::should_dispatch_bestofn` implements this predicate exactly.

#### PDR-RTV Flag

Derive `pdr_rtv`:
`pdr_rtv = budget >= ${CLAUDE_PDR_RTV_BUDGET_FLOOR:-10} AND critical == true`

The default trigger floor is `budget >= 10` AND `critical == true` (both clauses required), NOT `budget >= 9 OR critical` (the prior OR-clause empirically over-spent on non-critical mid-budget work). The `CLAUDE_PDR_RTV_BUDGET_FLOOR` env var (range 5–15) provides opt-in override for operators wanting an empirical lower-floor experiment, but the AND-clause still requires `critical == true` regardless of floor. Migration plan to relax the trigger (e.g. back to OR semantics, or floor below 10) is documented in `skills/pdr-rtv/SKILL.md` § Anti-Patterns: only after `/harness:eval-model-effectiveness` confirms ≥5% Pass@1 lift on the harness regression suite at the relaxed trigger.

PDR-RTV is mutually exclusive with Best-of-N at dispatch time (when both fire, PDR-RTV wins as the strictly stronger variant). The cost is roughly 4-5× standard Build (vs Best-of-N's 2-3×) — justifying the tightened conjunctive trigger.

#### Output

Always print one of:
```
[Intake] Best-of-N: enabled (reason: T6+budget>=7+critical)
```
or:
```
[Intake] Best-of-N: enabled (reason: user-override)
```
or:
```
[Intake] Best-of-N: disabled
```

Always print one of:
```
[Intake] PDR-RTV: enabled (reason: critical AND budget>=10)
```
or:
```
[Intake] PDR-RTV: disabled
```

Persist all three to `pipeline-state/{task-id}/intake.md` frontmatter:
- `task_class: {the classification from Step 1}`
- `bestofn: true|false`
- `pdr_rtv: true|false`

### Step 2e: Contract Identification (MANDATORY)

Identify what *contracts* the task touches before routing. Contracts are the public surface of the change — if a contract changes, downstream code (tests, callers, sibling modules, external consumers) is affected. Surfacing them at intake feeds Tier 0 (Contracts) of the Proof-of-Correctness ladder (`protocols/engineering-invariants.md` § Proof of Correctness) and the build-implementation "Write Contract Assertions" step (`skills/build-implementation/SKILL.md` § ATDD).

Scan the request text and any existing CLAUDE.md / project layout for changes to:

| Contract Class | Examples |
|---|---|
| **Public function signatures** | New/changed exported functions, their argument types and return types |
| **Types / structs added or changed** | TypeScript interfaces, Python dataclasses, Go structs, Rust traits — anything other modules import |
| **JSON schemas** | Request/response bodies, event payloads, config files with a versioned schema |
| **OpenAPI paths** | New routes, changed methods, modified status codes, query/path/body parameters |
| **DB schemas** | New tables, columns, indexes, constraints, foreign keys, RLS policies |
| **Invariants** | "X is always non-empty", "Y is monotonic in time", "Z and W are mutually exclusive" |

Persist the findings to `pipeline-state/{task-id}/intake.md` as a `## Contracts Touched` section AND mirror the list in the frontmatter as `contracts_touched:` (YAML list). The architect at Plan phase reads this section to derive Tier 0 contract assertions; the build engineer writes those assertions RED first.

```markdown
## Contracts Touched

- types/structs added or changed: `User`, `Session.AuthState` (lib/auth/types.ts)
- JSON schemas: `POST /v1/sessions` request body (added `mfa_token: string?`)
- OpenAPI paths: `/v1/sessions` POST 401 response shape
- DB schemas: `sessions.mfa_verified` BOOLEAN NOT NULL DEFAULT false
- public function signatures: `validateMfaToken(token: string, userId: UUID): Promise<MfaResult>`
- invariants: "a session is `mfa_verified=true` → `last_mfa_at` is non-null and within 30d"

# If the task touches no contracts (pure UI copy, log format tweak, README), say so:
- (none) — change is internal/cosmetic; no public surface affected. Tier 0 contracts skipped per protocols/engineering-invariants.md § Proof of Correctness.
```

Output a one-line summary:

```
[Intake] Contracts Touched: N items (function-sigs=A, schemas=B, db=C, invariants=D) | (none — internal/cosmetic)
```

If `(none)`, this is the explicit justification for skipping Tier 0 — record it so the Final Gate's patch-critique step can verify the skip is honest.

### Step 3: Pre-flight Check

Before invoking pipeline, verify and auto-fix:
1. **CLAUDE.md** — if not present, check if the working directory is also empty (no `package.json`, `Gemfile`, `go.mod`, `pyproject.toml`, `Cargo.toml`, `pom.xml`, no `src/` or `app/` or `lib/` directory). If empty AND the request describes building something new → classify as **Greenfield** and route to `/harness:greenfield-scaffold`. If not empty but just missing CLAUDE.md → invoke `/harness:project-setup`. Do not ask.
2. **In-progress pipeline** — check `pipeline-state/*-pipeline.md`. If found, automatically invoke `/harness:pipeline-resume` instead of starting a new pipeline. Inform the user: "Found in-progress pipeline [name]. Resuming from [phase]."
3. **Feature branch** — if on `main`/`master` and the work is a feature, refactor, or bug fix: automatically create and switch to a feature branch. Branch name: `feat/[kebab-case-summary]`, `fix/[kebab-case-summary]`, or `refactor/[kebab-case-summary]`. Do not ask — just create it.
4. **Working tree clean** — if uncommitted changes exist, warn the user before proceeding. Do not auto-commit — the user may have in-progress work.
5. **Test runner worktree exclusion** — on first pipeline run in a project, check that the test runner config excludes `.claude/worktrees/`. If not configured, add the exclusion automatically (Jest: `testPathIgnorePatterns`, pytest: `testpaths`, rspec: `--exclude-pattern`).
6. **Baseline tests** — run the project's test command (from CLAUDE.md Commands). If tests fail before we start, warn the user.

### Step 4: Route to Pipeline

Output the classification and route:

```
[Intake] task_id: {task-id}
[Intake] Classification: [type]
[Intake] Complexity: [small/medium/large] ([N] files, [coverage], [scope])
[Intake] Criticality: [critical/standard]
[Intake] Best-of-N: [enabled/disabled]
[Intake] Entry skill: /[skill-name]
[Intake] Pipeline phases: [list]
```

The `[Intake] task_id:` line is read by `hooks/intake-fingerprint-audit.sh` (PostToolUse) to resolve the intake.md path for forensic emit. Single-source — NO mtime fallback. Emit exactly once per intake (the hook resolves the last occurrence defensively if duplicated).

Then invoke `/harness:pipeline` (or the appropriate skill for non-pipeline work).

## Phase Output

```
Verdict: ROUTED (informational — no gate)
Next: /harness:pipeline, /harness:tech-spike, /harness:epic-breakdown, or direct answer
Classification: [feature/refactor/bug/spike/epic/question/setup]
Complexity: [small/medium/large]
```
$ARGUMENTS

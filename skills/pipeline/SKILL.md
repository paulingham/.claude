---
name: "pipeline"
description: "Use when user wants to Autonomous pipeline orchestration: classifies work, determines phases, tracks state via tasks, invokes skills in sequence, manages review loops and error recovery. The conductor that replaces manual orchestration. Use at the start of any implementation work."
---

# Pipeline Orchestration

## What This Skill Does

The autonomous conductor for the delivery pipeline. Takes a task, determines which phases apply, and drives skills in sequence — tracking state, managing review loops, and handling failures.

## When to Invoke

- Immediately after classifying work type (feature, refactor, bug fix)
- The `/harness:intake` skill invokes this, or the orchestrator invokes it directly after the pre-flight protocol

## Golden Path (Happy Case)

The linear happy-case sequence for a standard feature (T4/T5, budget 7–9, non-critical). Conditional
branches (multi-repo, scaffolding, Best-of-N/PDR-RTV, recovery loops) are noted but off this path.

1. **Tier Guard** (Step 1.0) — read `tier_emitted` from intake.md → T4/T5/T6 continue; T0–T3 re-route out.
2. **Classify + Pre-flight** (Steps 1–2) — pipeline scale; CLAUDE.md + greenfield checks.
3. **Create Pipeline State** (Step 2c) — write `pipeline.md` (the SSOT).
4. **Plan Cache Lookup** (Step 2c-bis) — MISS (default) → continue to spec-grounding + architect.
5. **Spec-Grounding** (Step 2c-ter) — EARS-tag ACs against codebase evidence (non-blocking).
6. **Recon + Architect** — context recon → architect produces plan.md.
7. **Plan Validation** (Step 2d) — challengers (product-reviewer + software-engineer) → PLAN_APPROVED.
8. **Build** (Step 3) — software-engineer in a worktree (TDD). *Standard dispatch for T4/T5; T6 critical uses Best-of-N / PDR-RTV — see Build Phase Dispatch below.*
9. **Code-review** — Build's final step (second model, different priors).
10. **Security Review** — separate phase (orthogonal concern).
11. **Final Gate** (Step 3) — verify + test + accept + patch-critique, in parallel.
12. **Reflect-write** (Step 4d, pre-Ship) — observation + /learn + commit learning to the feature branch.
13. **Ship** (Step 4c) — /harness:pr-creation → PR_CREATED.
14. **Deploy** (Step 5) — conditional; auto on merge for medium/large.
15. **Reflect** (Step 7) — analytics + qualitative reflection + state cleanup.

Everything below expands these steps with the conditional branches.

## Process

### Step 1.0: Tier Guard (MANDATORY first step)

Before any pipeline work, read `tier_emitted` from `$state_dir/{task-id}/intake.md` frontmatter (set by `/harness:intake` Step 1.5 Fingerprint per `protocols/work-class-routing.md`). The tier determines whether `/harness:pipeline` continues or exits with a re-route.

| Tier | Route | Status |
|---|---|---|
| **T0** (Question / Spike) | Re-route to direct answer or `/harness:tech-spike` | Pipeline halts (NO state file created) |
| **T1** (Doc-only) | Re-route to lightweight worktree subagent (tracked-doc edits) | Pipeline halts (NO state file created) |
| **T2** (Config-only) | Re-route to `/harness:harness-config` | Pipeline halts (NO state file created) |
| **T3** (Mechanical sweep) | Re-route to `/harness:batch-pipeline` | Pipeline halts (NO state file created) |
| **T3H** (Trivial code change) | Continue to trimmed lane (Build + diff-only standard code-reviewer + Ship; SKIP Plan, Plan-Validation, Security-Review) | Pipeline proceeds (state file created) |
| **T4** (Bug fix) | Continue to Step 1 (lightweight pipeline) | Pipeline proceeds |
| **T5** (Standard feature) | Continue to Step 1 (standard pipeline) | Pipeline proceeds |
| **T6** (Critical / cross-cutting) | Continue to Step 1 (heavy: Best-of-N or PDR-RTV) | Pipeline proceeds |

Status line — always emit one of:

```
[Pipeline] Tier guard: T0 → direct answer / /harness:tech-spike
[Pipeline] Tier guard: T1 → lightweight worktree subagent (tracked-doc edits)
[Pipeline] Tier guard: T2 → /harness:harness-config
[Pipeline] Tier guard: T3 → /harness:batch-pipeline
[Pipeline] Tier guard: T3H → /harness:pipeline (trimmed lane)
[Pipeline] Tier guard: T4 → /harness:pipeline (lightweight)
[Pipeline] Tier guard: T5 → /harness:pipeline (standard)
[Pipeline] Tier guard: T6 → /harness:pipeline (heavy)
```

T3H is a CONTINUE tier: it creates a pipeline state file and runs the trimmed lane — Build (full TDD, Iron Law 1 failing-test-first) + diff-only standard code-reviewer + Ship + Reflect. Plan, Plan-Validation, and Security-Review are skipped because the change is ≤1 file / ≤15 changed lines / no tests / no security surface / internal-shape-only. Iron Law 1 still applies inside Build.

**Scope-overflow abort (T3H → T4 upshift):** If the build engineer's actual diff exceeds 1 file OR 15 changed lines mid-build, ABORT the trimmed lane and upshift to T4 — re-enter the standard pipeline at Plan (so the change receives Plan + Plan-Validation + Security-Review). The prediction is not ground truth; the diff is.

**Reflect + telemetry:** T3H STILL runs Reflect (Iron Law 7) and emits the deploy_outcome companion record carrying tier_emitted: T3H so /harness:forensics computes a T3H-specific escape rate.

For T0-T3, **Pipeline halts (NO state file created)** — the dispatch target (direct answer / `/harness:harness-config` / `/harness:batch-pipeline` / lightweight worktree subagent) is invoked instead. Pipeline state file (`$state_dir/{task-id}/pipeline.md`) is created only at Step 2c (which runs for T3H and T4-T6). This Step 1.0 is the cost-discipline lever — T1 doc edits no longer burn ~12-15 subagent spawns through a full pipeline shape.

T4 and T5 both route into the standard (non-heavy) pipeline (neither uses the T6 heavy Build variants); the fingerprinter does not emit T5 today (Phase 3 deferred).

If `tier_emitted` is missing from intake.md (legacy intake or fingerprint error), default to T4+ behaviour (safety-bias — never under-dispatch). Log the missing-tier condition to the pipeline state file once it is created.

### Step 1: Classify Work and Determine Pipeline

| Work Type | Entry Skill | Pipeline Phases |
|-----------|-------------|-----------------|
| Feature (micro) | `/harness:build-implementation` | Plan → Plan Validation → Build (incl. code-review) → Security Review → Ship |
| Feature (small) | `/harness:build-implementation` | Plan → Plan Validation → Build (incl. code-review) → Security Review → Verify → Ship |
| Feature (medium) | `/harness:build-implementation` | Plan → Plan Validation → Build (incl. code-review) → Security Review → Verify → Test → Accept → Ship → Deploy |
| Feature (large) | `/harness:build-implementation` | Plan → Plan Validation → Build (incl. code-review) → Security Review → Verify → Load Test → Test → Accept → Ship → Deploy |
| Refactor | `/harness:refactor` | Plan → Plan Validation → Build (incl. code-review) → Security Review → Verify → Test → Accept → Ship |
| Bug Fix | `/harness:bug-fix` | Plan → Plan Validation → Build (incl. code-review) → Security Review → Verify → Test → Accept → Ship → Deploy |
| Spike | `/harness:tech-spike` | Spike only (no pipeline) |
| Planning | `/harness:epic-breakdown` | Plan only (produces stories for future pipelines) |

**Pipeline scale tiers:**
- **T3H (trimmed lane)**: ≤1 file, ≤15 changed lines, internal-shape-only → Build (full TDD) + diff-only standard code-reviewer + Ship + Reflect. SKIP Plan, Plan-Validation, Security-Review.
- **Micro**: 1 file, less than 5 lines changed, no behavior change → Plan + Plan Validation + Build (incl. code-review) + Security Review + Ship
- **Small**: 1-3 files, isolated change → Plan + Plan Validation + Build (incl. code-review) + Security Review + Verify + Ship
- **Medium/Large**: Full pipeline. No phase is skipped.

All T4-T6 tiers include Plan + Plan Validation. The `/harness:learn` system may create instincts to adjust this per project/pattern.

### Step 2: Pre-flight Checks (MANDATORY before pipeline state is created)

**Run these checks in order. Each is a hard gate — do not proceed until it passes.**

#### 2-A: CLAUDE.md check
Check for `.claude/CLAUDE.md` or `CLAUDE.md` at the project root.
- **Missing** → invoke `/harness:project-setup` as a blocking subagent (worktree). Wait for `PROJECT_SETUP_COMPLETE` before continuing. Do not ask the user — just run it.
- **Present** → read it and confirm no conflicts with global rules.

#### 2-B: Greenfield check (runs BEFORE architect, BEFORE pipeline state)
Check whether the working directory has no recognizable project file (`package.json`, `Gemfile`, `go.mod`, `pyproject.toml`, `Cargo.toml`, `pom.xml`) AND no `src/`, `app/`, or `lib/` directory.
- **Greenfield detected** → invoke `/harness:greenfield-scaffold` via the Skill tool. **This is a BLOCKING gate.** The pipeline cannot proceed to the architect or any other phase until `/harness:greenfield-scaffold` returns `GREENFIELD_SCAFFOLD_COMPLETE`. The orchestrator must NOT attempt any manual project bootstrap (no `npm init`, no `git init`, no writing `.gitignore` — delegate everything to the greenfield scaffold agent).
- **Not greenfield** → continue.

### Step 2c: Create Pipeline State

**MANDATORY**: Create a structured pipeline state file at pipeline start. This is the single source of truth for pipeline state — it survives context compaction.

The canonical destination is the per-task subdir layout: `$state_dir/{task-id}/pipeline.md` (workstream variant: `$state_dir/workstreams/{ws}/{task-id}/pipeline.md`). When `state_dir` resolves to its default (`$HARNESS_DATA/pipeline-state`), this becomes `$HARNESS_DATA/pipeline-state/{task-id}/pipeline.md`. The legacy flat form `$state_dir/{task-id}-pipeline.md` is read-tolerated during the 90-day DUAL_PATH soak (see `protocols/pipeline-protocol.md` § Structured Pipeline State) but MUST NOT be used for new pipelines.

```
pipeline-state/[feature-name]/pipeline.md
---
task_id: [feature-name]
phase: build
verdict: in_progress
timestamp: [ISO 8601]
scale: [micro/small/medium/large]
branch: [branch name]
critical: [true|false]
---

## Pipeline: [feature name]
Started: [date]
Classification: [feature/refactor/bug]

## Phases
- Plan: pending
- Plan Validation: pending
- Scaffold: pending (or N/A if no scaffolding needed)
- Build: pending  # WHY: code-review runs as Build's final step (see rules/core.md § Pipeline Phase Order)
- Security Review: pending
[...other phases per scale...]
- Ship: pending

## Key Files
[list as discovered]
```

Update this file as each phase completes with verdict, artifacts, and agent summaries.

**Mirror the `critical`, `task_class`, and `bestofn` flags from intake.** Read all three from `$state_dir/{task-id}/intake.md` (set by intake Steps 2d and 2d-bis) and write them into the pipeline state frontmatter on creation. This ensures `/harness:pipeline-resume` preserves the dispatch decision across context compaction so the Build phase still routes correctly.

**Do NOT dual-write to memory/.** The `pipeline-state/` file is the sole authority. Use `/harness:pipeline-resume` to recover state across sessions.

**Discussion context:** If a discussion file exists (`$state_dir/{task-id}/discussion.md` from intake Step 2b), reference it in the pipeline state under `## Intake Discussion` and pass its decisions to the architect during the Plan phase.

### Workstream Support

If a workstream is active (check `$state_dir/workstreams/*/workstream.md` for `status: active` entries, or check if the user specified a workstream):
- Create pipeline state in `$state_dir/workstreams/{workstream}/` instead of the default root
- Use branch convention: `{workstream-branch-prefix}{task-branch}` (e.g., `feat/auth/login-page`)
- Set `CLAUDE_PIPELINE_TASK_ID` to include workstream prefix for trajectory recording

If no workstream is active, use the default `pipeline-state/` directory (existing behavior, no change).

### Step 2a: Multi-Repo Detection (Automatic)

If intake flagged `multi_repo: true`, or if a manifest exists in `~/.claude/manifests/`:

1. **Read or create manifest**: See `protocols/multi-repo-protocol.md` for format and auto-creation triggers
2. **Resolve repo paths**: Verify all manifest repos exist locally. If a planned repo doesn't exist yet, it will be created during scaffold (Step 2b)
3. **Add `manifest:` to pipeline state frontmatter** with the manifest path
4. **Add `## Repos` section** to pipeline state tracking per-repo phases
5. **Determine dispatch mode**: Which repos need build agents? Which need PRs?

If no multi-repo signals → skip this step entirely (single-repo mode, no change to existing behavior).

### Step 2b: Pre-Build Scaffolding (Conditional)

Before the Build phase, check BOTH the task requirements AND the project state. Scaffolding triggers on missing project infrastructure — not just what the task description says. For example, if a CLAUDE.md exists but the project has no Dockerfile, no design system, or no observability, detect and scaffold those automatically.

| Task Signals | Scaffold Skill | What It Produces |
|-------------|---------------|-----------------|
| New API endpoints, REST resource | `/harness:api-scaffold` | Route stubs, controllers, validation, OpenAPI spec |
| Schema change, new table, add column | `/harness:db-migration` | Migration files, index strategy |
| No Dockerfile, no CI/CD, new project | `/harness:infra-scaffold` | Dockerfile, docker-compose, CI/CD pipeline, health endpoints |
| No logging/monitoring configured | `/harness:observability-setup` | Logger config, metrics, tracing, alerting |
| Voice skill/IVR needed | `/voice-scaffold` | Intent model, handler stubs, SSML templates |
| New channel for existing product | `/bff-scaffold` | Channel-specific BFF layer, transformers, gateway route |
| New microservice extraction | `/microservices-scaffold` | Service template, gateway config, tracing. Auto-creates GitHub repo from manifest config |
| Extract module to own repo | `/service-extraction` | New repo via manifest config, code migration, contracts, PRs in both repos |
| New repo needed (from architect plan) | GitHub repo creation | Reads manifest `## Services > GitHub`, creates repo, clones, runs `/harness:project-setup` |
| Empty directory, no project files | `/harness:greenfield-scaffold` | Full project bootstrap: framework, DevX, design system, infra, seed data |
| Frontend feature + no design brief | `/harness:creative-direction` | Design brief: fonts, palette, layout, interaction paradigm |
| Frontend project with no design system | `/harness:design-system-init` | Tokens, Tailwind config, primitive components, dark mode |

Scaffolding is NOT a gate — it produces files and structure that the Build phase then fills with business logic via TDD. Invoke scaffolding skills via the Skill tool (they delegate to the appropriate agent in a worktree).

**Dependency installation is NOT scaffolding.** Adding a package to `package.json` is part of the Build phase, not a pre-build step. Include dependency requirements in the build agent's prompt.

**Detection is automatic.** Check project state directly:

**Greenfield detection (check FIRST, before all other scaffolding):**
If the working directory has no recognizable project file (`package.json`, `Gemfile`, `go.mod`, `pyproject.toml`, `Cargo.toml`, `pom.xml`) AND no `src/` or `app/` or `lib/` directory: this is a greenfield project. Invoke `/harness:greenfield-scaffold` which handles ALL bootstrapping (framework, DevX, design system, infrastructure, seed data). After `/harness:greenfield-scaffold` completes, re-run the scaffold detection table — existing skills will detect any remaining gaps.

- Frontend feature detected (changed files include `.tsx/.jsx/.vue/.svelte`) AND no `$state_dir/{task-id}/design-brief.md` exists AND no established distinctive branding (tokens.css has only default values or doesn't exist)? → `/harness:creative-direction` FIRST
- No `Dockerfile`? → `/harness:infra-scaffold`
- No `styles/tokens.css` and no `theme.extend.colors` in Tailwind config? → `/harness:design-system-init`
- No logging config and task touches backend? → `/harness:observability-setup`
- Task needs new endpoints but no OpenAPI spec or routes exist? → `/harness:api-scaffold`

**Ordering when multiple scaffolds trigger:** `/harness:creative-direction` → `/harness:design-system-init` → other scaffolds → `/harness:build-implementation`. Creative direction produces the brief; design-system-init consumes it to generate tokens; build uses both.

If the project already has established infrastructure, design system, and patterns, skip scaffolding.

### Step 2c: Cross-Service Checks (Conditional)

If the project CLAUDE.md contains a `## Service Context` section with upstream/downstream services:

1. Read the service context to identify affected contracts
2. If the current change modifies a contract file (OpenAPI spec, Protobuf, event schema): invoke `/cross-service-pipeline` BEFORE the Build phase to verify compatibility and generate a deployment plan
3. After Ship phase, if cross-service deployment is needed: output the deployment plan with service order and flag any manual coordination required

### Step 2c-bis: Plan Cache Lookup (Stage 0 of Plan Phase)

BEFORE dispatching architect or recon, invoke `skills/plan-cache-lookup/SKILL.md`. The skill resolves `CLAUDE_PLAN_CACHE_MODE`, computes the `(task_class, repo_hash, gear, critical)` cache key, and emits exactly one of:

- `PLAN_CACHE_HIT` — the Haiku adapter has written `$state_dir/{task-id}/plan.md` with `cache_hit: true` and the resume-safety stub `$state_dir/{task-id}/architect-context.md`. Skip Stage 1 (recon) and Stage 2 (architect); advance directly to Step 2d (Plan Validation). Plan Validation challengers MUST skip the citation-alignment grader on `cache_hit: true` plans (Domain D7).
- `PLAN_CACHE_MISS` — `reason ∈ {no-template, disabled, shadow-mode, adapter-rejected, ...}`. Fall through to the normal Plan Phase Dispatch (Stage 1 recon + Stage 2 architect) IN THIS SAME PIPELINE. Iron Law 6: `adapter-rejected` is never deferred to a follow-up pipeline.

Until Slice F flips `CLAUDE_PLAN_CACHE_MODE` to `shadow`, the resolver hard-defaults to `off` and the skill short-circuits to `MISS reason=disabled` — partial-merge-safe by construction (LOW-eng-3).

Full wiring: `orchestrator/parallel-dispatch-details.md` § Plan Phase Dispatch (Stage 0).

### Step 2c-ter: Spec-Grounding (Stage 0 of Plan Phase)

After `PLAN_CACHE_MISS` from Step 2c-bis and BEFORE dispatching Stage 1 recon or Stage 2 architect, invoke `skills/spec-grounding/SKILL.md`. The skill spawns a spec-grounding subagent that:

1. Reads raw ACs from `$state_dir/{task-id}/intake.md`.
2. Calls the Python helper (`skills/spec_grounding/_lib/grounding.ground_acs()`) — pure-Python pathlib/re traversal of the codebase (bounded: max 5000 files, max 1MB per file; skips `.git/`, `.claude/worktrees/`, binary files, OSError/UnicodeDecodeError files silently) plus guarded `recall.search()` (degrades to `[]` if DB absent).
3. Writes `$state_dir/{task-id}/spec-grounding.md` with EARS-tagged ACs and per-AC citations.
4. Emits exactly one of:
   - `GROUNDED` — all ACs resolved against codebase or recall evidence.
   - `GROUNDING_GAPS` — one or more ACs have `[grounded: gap]`. **Non-blocking.** The pipeline falls through to Stage 1 recon + Stage 2 architect regardless. Gap ACs are listed in `spec-grounding.md` § Gaps; the architect reads this section and supplies citations for gap ACs in Artifact 2.

**GROUNDING_GAPS is never a blocking verdict.** The architect proceeds whether the verdict is `GROUNDED` or `GROUNDING_GAPS`. Skip this step only on `PLAN_CACHE_HIT` — the cached plan already contains grounded ACs.

### Step 2d: Plan Validation Gate (ALL pipelines)

After the architect produces a plan, validate it before proceeding to Build.

**Prerequisites**:
- Architect has produced plan output (from `/harness:epic-breakdown` or inline design)
- Plan includes `## Alternatives Considered` section (if missing, re-spawn architect with correction prompt — does not count as a challenge round)

**Mode detection**:
- Check `CLAUDE_PIPELINE_MODE` env var
- `autonomous` → spawn challenger team
- Unset / `interactive` → present plan to user

#### Interactive Mode

1. Present the architect's plan to the user:
   - Approach summary
   - Vertical slices with ACs and estimates
   - Alternatives considered with rationale
   - Parallel batch grouping
2. Wait for user approval (the user reviews and responds)
3. On approval: mark `Plan Validation: completed -- PLAN_APPROVED` in pipeline state
4. On feedback: re-spawn architect with user feedback (max 2 rounds)
5. On explicit rejection: mark `Plan Validation: completed -- PLAN_REJECTED`, stop pipeline

#### Autonomous Mode

1. Write architect's plan to `$state_dir/{task-id}/plan-validation.md`
2. Spawn challengers as team (parallel):

   ```
   Agent({
     name: "plan-reviewer",
     team_name: "pipeline-{task-id}",
     subagent_type: "product-reviewer",
     prompt: "[Plan Challenger - Product Reviewer template from
       orchestrator/parallel-dispatch-details.md]
       Plan under review: {architect_output}"
   })

   Agent({
     name: "plan-engineer",
     team_name: "pipeline-{task-id}",
     subagent_type: "software-engineer",
     prompt: "[Plan Challenger - Software Engineer template from
       orchestrator/parallel-dispatch-details.md]
       Plan under review: {architect_output}
       NOTE: This is a plan review, not implementation.
       Do NOT create files or write code."
   })
   ```

3. Collect verdicts:
   - Both APPROVE → `PLAN_APPROVED`, shut down challengers, proceed to Build
   - Either CHANGES_REQUESTED →
     a. Merge feedback into combined action items
     b. Re-spawn architect (subagent) with: original plan + combined feedback
     c. Present revised plan to the SAME challengers (context preserved via SendMessage)
     d. Only the rejecting challenger re-reviews (targeted re-review)
     e. Max 2 total rounds
   - Round 2 still rejected → `PLAN_ESCALATED`
     - Output `VERDICT: PLAN_ESCALATED` with full context
     - Pipeline stops (autonomous: ticket transitions to Blocked)
   - **PRECEDENCE NOTE**: The `Any single PLAN_FEASIBILITY_REJECTED` rule below is evaluated BEFORE the re-plan branch. A split case (one reject + one overturn) resolves to PLAN_FEASIBILITY_REJECTED, never to re-plan.
   - **M1 aggregation (split case)**: Any single PLAN_FEASIBILITY_REJECTED (even if the other challenger APPROVEs or APPROVE-with-overturn) → emit PLAN_FEASIBILITY_REJECTED. Mirror the "Either CHANGES_REQUESTED" single-rejector semantics: one premise-veto is conservative-sufficient. SURFACE to the user (distinct from silent CHANGES_REQUESTED re-work); write feasibility_drift recording BOTH challenger verdicts; pipeline stops pending user decision (autonomous: ticket → Blocked with the reject-brief). Do NOT fall through to re-plan.
   - **Re-plan branch (both challengers overturn a reject)**: Architect said FEASIBILITY_REJECTED AND BOTH challengers emit APPROVE-with-overturn (and neither emits PLAN_FEASIBILITY_REJECTED) → re-spawn architect to author the full plan it skipped (NOT a CHANGES_REQUESTED re-work; logged in feasibility_drift with overturned:true), then re-validate. Do NOT stop.

4. After validation completes: shut down challengers

**Status reporting**:
```
[Plan Validation] MODE -- {interactive/autonomous}
[Plan Validation] TEAM PHASE -- plan-reviewer + plan-engineer spawned
[Plan Validation] VERDICTS -- plan-reviewer: {verdict}, plan-engineer: {verdict}
[Plan Validation] COMPLETE -- PLAN_APPROVED (round {N})
```

### Step 3: Execute Phases in Order

For each phase:
1. Update the memory file to mark the phase as `in_progress`
2. **Sequential read-only phases** (Test analysis, Accept): Invoke the skill via the Skill tool
2b. **Sequential write-capable phases** (Build, Verify Tier 3, QA gap-fill, scaffold): Spawn agent via Agent tool with `isolation: "worktree"`, instructing them to read and execute the skill file at `~/.claude/skills/[name]/SKILL.md`
3. **Parallel phases**: Use Parallel Dispatch Protocol (see `protocols/parallel-dispatch-protocol.md`) — spawn agents in a single message, each reading their own skill file
4. Read the Phase Output (Verdict, Next, Artifacts)
5. At each phase boundary, invoke `hooks/phase-boundary-compress.sh <completed-phase> <next-phase>` (advisory): measures tokens_before/tokens_after, emits one record to `metrics/{session}/phase-boundary.jsonl`. Does not rewrite the handoff. Escape hatch: `CLAUDE_DISABLE_PHASE_BOUNDARY_COMPRESS=1`.
6. If verdict is a failure/rejection: handle per Step 4 (Recovery)
7. If verdict is success: update memory file with verdict and artifacts, advance to next

#### Build Phase Dispatch — Variant Routing (precedence: `pdr_rtv > bestofn > standard`)

Read `pdr_rtv` and `bestofn` from the pipeline state frontmatter (mirrored from `$state_dir/{task-id}/intake.md` at pipeline creation; computed by intake Step 2d / 2d-bis). The **PDR-RTV check runs first** because it is the strictly stronger variant when both flags fire.

##### PDR-RTV Check (runs first)

- If `pdr_rtv == true` (computed by intake Step 2d-bis as `budget >= ${CLAUDE_PDR_RTV_BUDGET_FLOOR:-10} AND critical == true`): dispatch via the **PDR-RTV Build Team** variant (see `orchestrator/parallel-dispatch-details.md` § PDR-RTV Build Team Dispatch). PDR-RTV runs T=2 iterations of N parallel rollouts (peak concurrent worktrees = N = 4 due to strict iteration serialisation), summary-based refinement, and pairwise tournament selection. The winner still proceeds through the normal Review → Final Gate → Ship gates.
- If `pdr_rtv == true AND bestofn == true`: PDR-RTV wins (strictly stronger). Log re-route to `$state_dir/{task-id}/pipeline.md` § Re-routes.
- Otherwise: fall through to the Best-of-N Check below.

**PDR-RTV Fallback**: on `PDR_NO_CONSENSUS` (insufficient green builds, all finalists rejected, or worktree-cap exceeded), silently re-route to Best-of-N → standard Build. Log the fallback in pipeline state under `## Re-routes` with `fallback_reason` enum (`worktree-cap-exceeded` | `insufficient-green-builds` | `all-finalists-rejected`). The pipeline never halts on a PDR-RTV failure and never asks the user.

##### Best-of-N Check

Read `bestofn` from the pipeline state frontmatter (mirrored from `$state_dir/{task-id}/intake.md` at pipeline creation; computed by intake Step 2d-bis as `critical OR user_override`, where `user_override` fires on the literal `[best-of-n]` token in the request text).

- If `pdr_rtv == false AND bestofn == true`: dispatch via the **Best-of-N Build Team** variant (see `orchestrator/parallel-dispatch-details.md` § Best-of-N Build Team Dispatch). This is not a separate skill — it is a dispatch mode of the Build Team that runs N candidate models in parallel and selects the winner. The winner still proceeds through the normal Review → Final Gate → Ship gates.
- If absent (older pipelines pre-flag): treated as `False` — use standard Build dispatch.
- Otherwise: use the standard Build dispatch (single-engineer subagent with worktree, or standard Build Team for multi-slice / multi-domain work).

**Best-of-N Fallback**: on `BEST_OF_N_FAILED` (e.g. insufficient candidates after env-var validation, or all candidates failed their own tests), automatically fall back to the standard Build dispatch and log the fallback in pipeline state under `## Re-routes` (e.g. `re-routed from best-of-n to standard build (reason: insufficient candidates)`). The pipeline never halts on a Best-of-N failure and never asks the user.

This check fires ONLY at Build dispatch. Scaffolding, Polish, Review, Final Gate, Ship, and Deploy are unaffected.

#### Polish Phase (Conditional: Budget >= 7)

After Build completes and before Review:
1. If Complexity Budget >= 7: invoke `/harness:polish` skill via subagent (Haiku model, worktree)
2. Polish agent reads changed files, fixes mechanical issues only (naming, dead imports, commented-out code)
3. Merge polish commits before dispatching reviewers
4. Skip for micro/small pipelines (Budget 5-6)

#### Adversarial Review (Conditional: Budget >= 10 OR sensitive code)

When the change scores Budget >= 10 OR touches auth/payment/data-deletion code:
- Spawn TWO code-reviewers (Reviewer-A: design focus, Reviewer-B: edge-case focus)
- Each reviews independently, produces separate verdicts
- Orchestrator merges findings: convergent findings = HIGH, divergent = MEDIUM
- Both must APPROVE to advance (standard threshold applies to each)
- See `orchestrator/parallel-dispatch-details.md` for dispatch template

#### Design QC (MANDATORY for Frontend Changes)

If changed files include `.tsx`, `.jsx`, `.vue`, `.svelte`, or CSS files:
1. Invoke `/harness:design-qc` as part of the Final Gate (parallel with verify + qa + accept)
2. Design QC runs the full DevOps lifecycle: install → build → start server → capture → stop
3. If `CAPTURE_FAILED` → the pipeline **BLOCKS**. Fix the build/server issue before proceeding
4. Screenshots are passed to the product-reviewer for visual validation
5. Product-reviewer MUST receive screenshots — no visual review without them
6. No silent skip — if frontend files changed, visual proof is required

#### Security Review + Code-review Dispatch (TEAM — always)

1. `TeamCreate("pipeline-{task-id}")` if not already created
2. Spawn reviewers as **teammates** (NOT independent subagents):
   - `Agent({ name: "code-reviewer", team_name: "pipeline-{task-id}", ... })`
   - `Agent({ name: "security-engineer", team_name: "pipeline-{task-id}", ... })`
3. On CHANGES_REQUESTED:
   - Spawn fix-engineer into the SAME team
   - After fix: `SendMessage` to the raising reviewer (still alive, has context)
   - Do NOT spawn a new reviewer subagent — use the persistent one
4. After both APPROVE: shut down reviewers

#### Final Gate (TEAM — always)

Spawn all Final Gate agents into the same team:
- `Agent({ name: "verifier", team_name: "pipeline-{task-id}", ... })` — `/harness:verify`
- `Agent({ name: "test-analyst", team_name: "pipeline-{task-id}", ... })` — `/harness:qa-test-strategy`
- `Agent({ name: "product-reviewer", team_name: "pipeline-{task-id}", ... })` — `/harness:product-acceptance`
- `Agent({ name: "design-qc", team_name: "pipeline-{task-id}", ... })` — `/harness:design-qc` (if frontend)

#### Accessibility Check (MANDATORY when frontend files changed, parallel with Design QC)

If changed files include `.tsx`, `.jsx`, `.vue`, `.svelte`, or CSS files:
- Spawn `/harness:accessibility-check` into the Final Gate team (parallel with `/harness:design-qc`)
- Passes collected changed-route URLs per SKILL.md Step 1 route-detection procedure
- A11Y_CHECK_FAILED → pipeline BLOCKS (same gate weight as CAPTURE_FAILED)
- A11Y_CHECK_SKIPPED → pipeline continues; scratchpad warning emitted
- No silent skip — if frontend files changed, accessibility gate is required

All agents assess the same final state independently. Shut down after all verdicts collected.

#### Parallel Phases (Dispatch Reference)

- **Security Review + Code-review**: teammates in pipeline team (see above)
- **Build (independent slices)**: multiple engineers dispatched in parallel worktrees
- **Final Gate**: teammates in pipeline team (see above)
- **Verify Tier 1+2**: independent tiers dispatched in parallel where applicable

All other phases (Build single slice, Polish, Ship) use sequential Skill tool invocation.

### Step 4: Recovery Loops

#### Plan Validation PLAN_CHANGES_REQUESTED
1. Re-spawn architect with combined challenger feedback
2. Re-submit revised plan to same challengers (context preserved via SendMessage)
3. Only the rejecting challenger(s) re-review (targeted re-review)
4. Maximum 2 total rounds. If still rejected:
   - Interactive: present to user with all context
   - Autonomous: PLAN_ESCALATED, pipeline stops

#### Plan Validation PLAN_ESCALATED (autonomous only)
1. Pipeline stops immediately
2. Output: VERDICT: PLAN_ESCALATED with plan, feedback, and rejection reasons
3. Ticket transitions to Blocked with full context comment

#### Plan Validation PLAN_FEASIBILITY_REJECTED
1. Surface the reject-brief to the user verbatim.
2. Write feasibility_drift to observations (4d-i) BEFORE the stop.
3. Pipeline stops; ticket → Blocked.
This is NOT the silent architect re-work of the PLAN_CHANGES_REQUESTED handler above — the drift signal (architect-said-X, reviewers-concluded-Y) MUST survive into forensics.
4. Light-gate variant: plan-self-validation emitted it as a self-judgment; same user-surface + same feasibility_drift write (architect_said == reviewers_concluded == FEASIBILITY_REJECTED, overturned:false). Distinct from the silent re-work path: user sees the reject-brief, feasibility_drift is written, pipeline does not loop.

#### Review CHANGES_REQUESTED
1. Spawn engineer (worktree) with specific findings
2. After fix: targeted re-review by raising reviewer(s) only, not full re-dispatch of both
3. Maximum 2 total rounds (initial + 1 re-review). If unresolved, escalate to user

#### Verify UNVERIFIED
1. Return to Build phase to fix failing tiers
2. Re-run Review (both skills)
3. Re-run Verify

#### QA GAPS_FOUND
1. QA engineer writes missing tests (in worktree)
2. Re-run `/harness:qa-test-strategy`

#### Accept APPROVED_WITH_CONDITIONS
1. Spawn engineer to address conditions
2. Re-run `/harness:product-acceptance`

#### Accept REJECTED
1. Return to Build phase with feedback
2. Re-run full pipeline from Build

#### Load Test PERFORMANCE_FAILED
1. Identify bottlenecks (database queries, missing indexes, no caching)
2. Return to Build phase to optimize
3. Re-run `/harness:load-test`

#### Deploy DEPLOY_FAILED or AUTO_ROLLBACK
1. `/harness:deployment-verification` triggered automatic rollback
2. Investigate failure cause from verification report
3. Create bug fix via `/harness:intake`, re-enter pipeline

#### PR_BLOCKED
1. Fix quality gate failures
2. Re-run `/harness:pr-creation`

### WRONG_SKILL Handling

When a skill returns `WRONG_SKILL: {guidance}`, the orchestrator automatically re-invokes the correct skill with the same task context. No user prompt. The re-invocation is logged to pipeline state as `re-routed from /{original-skill} to /{target-skill} (reason: {guidance})`.

- **Maximum one re-route per pipeline** — a second `WRONG_SKILL` escalates to user.
- The target skill is parsed from the guidance text (e.g., `WRONG_SKILL: use /harness:module-extraction` → target is `/harness:module-extraction`).
- Routing is recorded in `$state_dir/{task-id}/pipeline.md` under a `## Re-routes` section.

### Step 4b: Extraction Assessment (Automatic, Post-Accept)

After Accept phase completes (APPROVED), check whether the codebase has grown to warrant service extraction:

1. Check the code-reviewer's output for **Extraction Candidate** flags (from the Review phase)
2. If extraction candidates were flagged with 3+ signals:
   - Report to user: "[Module] has crossed extraction thresholds. Recommend running `/service-extraction` after this feature ships."
   - If the user has previously configured auto-extraction (via `CLAUDE_AUTO_EXTRACT=true` in settings.json env), invoke `/service-extraction` automatically after Ship phase
   - Otherwise: add to pipeline output as a recommended follow-up action

This assessment is zero-cost — it reads the existing review output. No additional analysis needed.

### Step 4d: Reflect-write (Pre-Ship)

> **Why pre-Ship, not post-Deploy?** Learning observations + instinct files must be committed to the feature branch so they ship inside the PR (not stranded as orphan chore(learning): commits on local main). That is why Reflect is split: the file-producing sub-steps run here (pre-Ship), and analytics + qualitative reflection + cleanup run at Step 7 (post-Deploy).

**MANDATORY** between Final Gate completion and Step 4c (Multi-Repo Ship / `/harness:pr-creation`). Relocates the two file-producing Reflect sub-steps (observation append + `/harness:learn`) to before `gh pr create` so the learning artifacts land inside the feature branch and ship with the PR — instead of as orphan `chore(learning):` commits stranded on local `main` while other PRs merge ahead.

Three sub-steps, in strict order. Each must complete before the next begins.

#### 4d-i. Per-Pipeline Observation Capture

Appends a single `record_type: "pipeline"` JSON record to `learning/{project-hash}/observations.jsonl` so the auto-learn gate (`auto-learn-gate.sh` Stop hook) and `mine_anti_patterns` consumer in `/harness:learn` see this pipeline.

Schema source of truth: `protocols/autonomous-intelligence.md` § Field reference. The `phases.patch_critic` block shape and the `persona_rejections` invariants are documented there; this step is the producer surface for the regular pipeline (the `batch-pipeline` skill writes the same shape from its Step 6).

##### JSON template (orchestrator emits at Reflect time)

```json
{
  "record_type": "pipeline",
  "timestamp": "<ISO 8601>",
  "session_id": "<session-id>",
  "pipeline_id": "<task-id>",
  "classification": "feature|refactor|bug",
  "phases": {
    "build": {
      "verdict": "BUILD_COMPLETE",
      "rounds": 1,
      "agents": [
        {"role": "software-engineer", "model": "claude-sonnet-4-6"}
      ]
    },
    "review": {"verdict": "APPROVE", "rounds": 1, "findings": 0},
    "verify": {"verdict": "VERIFIED", "tiers_passed": 3},
    "test": {"verdict": "COVERED", "coverage": 92},
    "accept": {"verdict": "APPROVED", "conditions": 0},
    "patch_critic": {
      "verdict": "PATCH_APPROVED",
      "rounds": 1,
      "mode": "multi-persona",
      "persona_rejections": []
    }
    // OPTIONAL: append `phases.sandbox_verify` when the Build phase's
    // Step 5b /harness:sandbox-verify gate ran and $state_dir/{task-id}/build.md
    // carries a `## Sandbox Verify` section. Schema documented in
    // protocols/autonomous-intelligence.md § Field reference.
    // Example: "sandbox_verify": {"verdict": "SANDBOX_VERIFIED",
    //                              "rounds": 1, "cost_estimate_usd": 0.12}
  },
  "scratchpad_findings": ["category:summary", ...],
  "rework": false,
  "duration_phases": 6,
  "complexity_budget": 9
  // OPTIONAL: "triggered_by_pipeline_id": "<prior-task-id>" — include ONLY when the
  // user confirmed the originating pipeline at intake (Discussion Persistence §
  // Impact on Implementation) or root-cause at bug-fix Step 0. OMIT when unknown;
  // NEVER write null — absence and null are forensically distinct.
}
```

##### Mode invariant for `phases.patch_critic.persona_rejections`

The field MUST be present (possibly empty array on PATCH_APPROVED) iff `mode == "multi-persona"`. It is **absent in single-critic** mode — DO NOT write `persona_rejections: null` (absence and explicit null are forensically distinct, and the consumer's malformed-shape detector treats `null` differently than absence). Use a conditional builder (Python `dict.pop` or `jq if/else`) to omit the key cleanly when not in multi-persona mode.

##### Severity threshold for `persona_rejections` entries

Only `CRITICAL`, `HIGH`, and `MEDIUM` rejections are recorded. `LOW` and `INFO` findings are excluded from `persona_rejections` — they do NOT fail a dimension per `agents/patch-critic.md`, so they must be omitted from the producer's writes. Each entry shape: `{persona ∈ {correctness, regression-risk, scope-creep}, dimension: int (1..5), severity ∈ {CRITICAL, HIGH, MEDIUM}}`.

##### Sandbox-safe append (Python)

The bash-write-guard hook denies raw shell redirects to `observations.jsonl` (per the `feedback_reflect_phase_quirks` instinct — bash `>>` is blocked even on orchestrator-writable paths). Use Python's `os.open` with `O_APPEND` instead:

```bash
python3 - <<'PY'
import json, os, time
record = {
  "record_type": "pipeline",
  "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  # ... fill in remaining fields per the JSON template above ...
}

# OPTIONAL: append `phases.sandbox_verify` when Step 5b ran. Detect by
# reading `$state_dir/{task-id}/build.md` and looking for the
# `## Sandbox Verify` section. Mirror the patch_critic absence rule:
# write the block IFF the section exists; never synthesise a default.
# Example fill:
#   record.setdefault("phases", {})["sandbox_verify"] = {
#       "verdict": "SANDBOX_VERIFIED",  # parse from build.md
#       "rounds": 1,                    # orchestrator round counter
#       "cost_estimate_usd": 0.0,       # null/0.0 when cost data unavailable
#   }
# When verdict == "SANDBOX_FAILED", populate `divergence_count` and
# `diverging_tests` (bounded at 20) via
# `hooks/_lib/sandbox_verify_observation.diverging_tests_from_build_md`.
# When verdict == "SANDBOX_SKIPPED", populate `skip_reason` from the
# build.md body line (`reason=...`).

# OPTIONAL: append `phases.plan_validation.feasibility_drift` IFF a
# feasibility pass ran. Detect via a `## Feasibility Finding` section in
# `architect-context.md`, OR the inline plan.md finding in the light gate.
# Absence-vs-null rule (mirrors persona_rejections at SKILL.md:520):
#   - ABSENT means no feasibility pass ran (pass-didn't-run, not "agreed FEASIBLE").
#   - PRESENT with overturned:false means the pass RAN and both parties agreed FEASIBLE
#     (L1: do NOT omit on FEASIBLE-agreed — that would make "pass ran, agreed" indistinguishable
#     from "pass never ran").
# Parse architect_said from the Feasibility Finding verdict line
# ("FEASIBILITY: FEASIBLE" or "FEASIBILITY: FEASIBILITY_REJECTED").
# Parse reviewers_concluded/overturned from the challenger verdicts (or, in the
# light gate, reviewers_concluded := architect_said, overturned := false).
# Example fill when pass ran:
#   record.setdefault("phases", {}).setdefault("plan_validation", {})["feasibility_drift"] = {
#       "architect_said": "FEASIBLE",          # or "FEASIBILITY_REJECTED"
#       "reviewers_concluded": "FEASIBLE",     # or "FEASIBILITY_REJECTED"
#       "overturned": False,                   # True when architect_said != reviewers_concluded
#   }
# When the pass did NOT run, omit the key entirely — do NOT write null.

# OPTIONAL: include triggered_by_pipeline_id when the originating pipeline is known.
# Primary source: read `discussion.md` § Impact on Implementation Triggered-by line.
# Fallback: engineer-identified at bug-fix Step 0. Absence-vs-null rule mirrors
# persona_rejections (SKILL.md:557): omit the key when absent — NEVER write null.
# Example fill when known (pseudo — the orchestrator parses the line inline; there is
# no real helper of this name):
#   triggered = read_triggered_by_from_discussion_md()  # pseudo: parse Triggered-by line
#   if triggered:
#       record["triggered_by_pipeline_id"] = triggered
#   # Otherwise: record.pop("triggered_by_pipeline_id", None) — omit entirely

path = os.path.expanduser("~/.claude/learning/<project-hash>/observations.jsonl")
os.makedirs(os.path.dirname(path), exist_ok=True)
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
try:
    os.write(fd, (json.dumps(record) + "\n").encode("utf-8"))
finally:
    os.close(fd)
PY
```

Append must complete BEFORE 4d-ii (`/harness:learn` reads `observations.jsonl` from disk) and BEFORE 4d-iii (feature-branch commit). The auto-learn-gate Stop hook reads new appended lines via a file-offset cursor; the sequencing is load-bearing.

#### 4d-ii. Learning Extraction (synchronous)

Invoke `/harness:learn` **synchronously** (NOT background-spawn) so the instinct `.md` files are flushed to disk before 4d-iii commits. This is a deliberate deviation from `protocols/reflection-protocol.md` § 6b's async dispatch — § 6b describes the legacy post-Ship variant; Step 4d is the pre-Ship variant and is synchronous by design to avoid a race between `/harness:learn`'s file writes and the worktree commit below.

`/harness:learn` analyzes session observations, pipeline analytics, and review findings. This:
1. Reads enriched observations for this session (tool usage with phase, role, outcome)
2. Reads pipeline analytics for this project (last N pipelines from `metrics/pipelines.jsonl`)
3. Reads review findings from the current pipeline's review state file (if it exists, before cleanup)
4. Detects patterns and creates/updates instinct files in `learning/instincts/`
5. Classifies review findings as "preventable by build agent" vs. "review-level only"
6. Converts preventable findings into build-targeted instincts (backward feedback loop)
7. Reports new/updated instincts to the orchestrator

The orchestrator reports learnings to the user (skip if nothing actionable). Every pipeline — whether it had rework or ran clean — feeds the learning flywheel.

#### 4d-iii. Feature-branch Commit (with fallback guard)

After 4d-i and 4d-ii complete, the orchestrator commits the newly-written learning files to the feature-branch worktree. The `learning/` path is partially `.gitignore`d (per `.gitignore` lines 53-58: only `learning/instincts/**` is tracked; per-project `learning/{project-hash}/observations.jsonl` is ignored). The `git add learning/` below picks up only the tracked instinct files; the ignored observations.jsonl is intentionally excluded — observations are local-only state.

```bash
if [ -d "$WORKTREE/.git" ]; then
  git -C "$WORKTREE" add learning/
  git -C "$WORKTREE" diff --cached --quiet || \
    git -C "$WORKTREE" commit -m "chore(learning): observation + instincts for {task-id}"
else
  echo "[reflect-write] worktree gone; falling back to post-merge commit on main" >&2
fi
```

The fallback guard preserves today's post-merge behaviour if the worktree was torn down before Step 4d ran. Iron Law 4 is honoured — all HEAD-mutating commands run via `git -C "$WORKTREE"`.

### Step 4c: Multi-Repo Ship (Automatic When Manifest Exists)

**Prerequisite**: Step 4d (Reflect-write) must have committed observation + instinct files to the feature branch before this step invokes `/harness:pr-creation`. Skipping Step 4d strands `chore(learning):` commits on local `main` post-merge — exactly the divergence symptom this ordering prevents.

When the pipeline has a manifest (multi-repo mode):

1. **Create PRs per repo** in dependency order (providers first):
   - For each repo with changes, run `/harness:pr-creation` in that repo's working directory
   - Each PR body includes `## Related PRs` with cross-references
   - Track all PRs in the pipeline state's `## PR Manifest` section
2. **Merge order enforcement**:
   - Provider PRs merge first (no dependencies)
   - Wait for CI to pass on merged provider
   - Consumer PRs merge after their dependencies are satisfied
3. **All PRs tracked** in pipeline state — the orchestrator monitors status via `gh pr view`

If single-repo mode (no manifest) → existing Ship behavior (one PR, no cross-references).

### Step 5: Deploy (Automatic for Medium/Large)

After Ship phase returns PR_CREATED:

> **Advisory CI-watch (pr-creation Step 5b):** Before the enforcing gate below,
> the orchestrator runs the advisory CI-watch sub-phase (`skills/pr-creation/SKILL.md`
> Step 5b). It polls `gh pr checks <pr-number>` (keyed off CI conclusion) until all
> runs conclude against the pushed headRefOid. On CI_RED, the fix loop re-enters
> automatically; on CI_GREEN, it proceeds here. The advisory watch and the enforcing
> gate are orthogonal — the watch drives the fix loop, the gate is the hard stop.

**Enforcing CI-green gate (BEFORE deploy auto-invoke):**

Run `skills/pipeline/lib/check-ci-green-gate.sh <PR_NUMBER>` before any deploy invocation.

- **Exit 0 (CI_GREEN)**: CI is conclusively green — proceed to merge-status check and deploy.
- **Exit 2 (CI_RED)**: CI is NOT conclusively green — **halt; do NOT invoke `/harness:deploy`**. Re-enter the in-cycle fix loop. The gate emits a human-readable block message naming the PR number, observed reason (e.g. `gh-error`, `empty-rollup`, `unknown-check-type:<token>`), and the override hint.

Operator escape: `CLAUDE_CI_GREEN_GATE=off` bypasses the gate with a loud warning. Use only when the failure is demonstrably pre-existing and unrelated to the current change.

1. Check PR merge status: `gh pr view [PR_NUMBER] --json state -q '.state'`
2. If `MERGED`: automatically invoke `/harness:deploy` → `/harness:deployment-verification`
3. If `OPEN`: inform user PR is ready for review. The deploy phase will run when the user returns after merge — `/harness:pipeline-resume` detects Ship=completed + Deploy=pending and auto-continues.

For micro/small pipelines: deploy is optional (inform user, don't auto-invoke).

#### Multi-Service Deploy (When Manifest Exists)

When the pipeline has a manifest with multiple repos and deploy targets:

1. Read `## Deploy Order` from manifest
2. Deploy in dependency order: providers first, then consumers
3. After each service deploys: run health check, verify `/harness:deployment-verification`
4. Only proceed to next service after current is DEPLOYMENT_VERIFIED
5. If any service fails: halt remaining deploys, rollback in reverse order
6. Cross-service smoke tests after all services deployed
7. Track per-service deploy status in pipeline state

Single-repo mode: existing behavior (one deploy, no cross-service checks).

### Step 6: Completion

When all phases are complete (including Deploy if applicable):
1. Update pipeline-state file: mark all phases as `completed`, record PR URL and deploy URL
2. Report PR URL (and deploy URL if deployed) to user
3. Output final pipeline summary with all agent contributions
4. DO NOT clean up state here — cleanup runs at Step 7d after analytics and reflection

### Step 7: Reflect

**MANDATORY** after every pipeline. Three sub-steps, in order:

#### 7a. Pipeline Analytics (before cleanup)

Capture quantitative pipeline metrics before state files are deleted:
```bash
bash ~/.claude/hooks/pipeline-analytics.sh {task-id}
```
This aggregates phase verdicts, agent counts, and review rounds into `metrics/pipelines.jsonl`. Must run before state file cleanup — cleanup runs at Step 7d, NOT at Step 6.

#### 7b. Qualitative Reflection

Run the reflection checklist from `protocols/reflection-protocol.md`.

If the pipeline experienced failures, >2 review rounds, or any recovery loop: invoke `/harness:forensics` before reflection. The forensics report provides evidence-based findings for the reflection checklist.

1. Review the pipeline execution for issues, surprises, and validated patterns
2. Identify improvements to rules, project CLAUDE.md, global CLAUDE.md, agent definitions, skills, or memory
3. Apply identified changes (delegate source file changes to agents)

#### 7b-bis. Per-Pipeline Observation Capture — RELOCATED to Step 4d-i

Moved pre-Ship so learning artifacts land in the PR (see Step 4d for full body: JSON template, mode invariant, sandbox-safe append).

#### 7c. Learning Extraction — RELOCATED to Step 4d-ii

Moved pre-Ship and invoked **synchronously** (NOT background-spawn) so instinct files are flushed before the Step 4d-iii feature-branch commit (see Step 4d; deviation from `protocols/reflection-protocol.md` § 6b async path is intentional).

#### 7d. Reflect Cleanup (Dual-Form During DUAL_PATH Soak)

After analytics, reflection, and learning are complete, remove the pipeline state files. Cleanup is dual-form during the 90-day DUAL_PATH soak (per `protocols/pipeline-protocol.md` § Structured Pipeline State):

0. **Pre-step — shadow-checkpoint refs**: delete every `refs/checkpoints/{task-id}/*` ref in the shared ref database (created by `hooks/shadow-git-checkpoint.sh`). Refs live in REPO_ROOT's ref db (per `git-worktree(1)` semantics — only `refs/heads/*` is per-worktree), so cleanup runs against `REPO_ROOT`, NOT against any individual worktree. Idempotent: zero refs → loop no-ops. Workstream variant: refs are NOT workstream-prefixed (task-id alone is unique), so the same loop covers both. Per-worktree counter file `$state_dir/{task-id}/checkpoint-counter-{slug}.txt` is removed by Form 1's `find -delete` below — no separate step.
1. **Form 1 — new-layout subdir cleanup**: empty the per-task subdir with `find -delete` (sandbox-safe — `rm -rf` on directories is denied by the sandbox even on orchestrator-writable paths). Workstream variant: same pattern under `$state_dir/workstreams/{ws}/{task-id}/`.
2. **Form 2 — legacy phase enumeration**: iterate the canonical phase list via `_psp_phase_list` (sourced from `hooks/_lib/pipeline-state-paths.sh`) and remove each `$state_dir/{task-id}-{phase}.md` file. **NEVER use a bare wildcard glob over the task prefix** — that matches prefix neighbours (e.g. cleanup of `tool` would delete `tool-timing-capture-*` files). R12 mitigation.
3. Approval token + trajectory have well-known names; remove them by exact path: `$state_dir/{task-id}-approval.token` and `$state_dir/{task-id}-trajectory.jsonl`.

> **WARNING — scope guard (2026-06-04 wipe incident)**: Form 1 cleanup MUST target
> `$task_dir` only (the per-task subdir). MUST NOT pass `$state_dir` or the whole
> `pipeline-state/` tree to `find -delete` — that would wipe every active pipeline's
> state in a concurrent-session environment. The 2026-06-04 wipe incident was caused by
> a command outside this snippet that targeted the whole tree. This snippet is safe as
> written; do not widen the scope.

Canonical cleanup snippet (mirrors what the orchestrator runs):

```bash
source ~/.claude/hooks/_lib/pipeline-state-paths.sh
state_dir="${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/pipeline-state"
task="{task-id}"
ws=""  # set to the workstream name when applicable

# Pre-step: delete shadow-git-checkpoint refs for this task-id.
# Refs live in REPO_ROOT's shared ref db (not per-worktree), so cleanup runs
# against REPO_ROOT. Idempotent — zero refs → while loop iterates zero times.
REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -n "$REPO_ROOT" ]; then
  git -C "$REPO_ROOT" for-each-ref --format='%(refname)' "refs/checkpoints/$task/" 2>/dev/null \
    | while IFS= read -r ref; do
        git -C "$REPO_ROOT" update-ref -d "$ref" 2>/dev/null || true
      done
fi

# Form 1: new-layout subdir. Use find -delete (rm -rf on dirs is sandbox-denied).
if [ -n "$ws" ]; then
  task_dir="$state_dir/workstreams/$ws/$task"
else
  task_dir="$state_dir/$task"
fi
if [ -d "$task_dir" ]; then
  find "$task_dir" -type f -delete
  find "$task_dir" -depth -type d -empty -delete
fi

# Form 2: legacy phase enumeration via _psp_phase_list (NO bare globs).
while IFS= read -r phase; do
  if [ -n "$ws" ]; then
    rm -f "$state_dir/workstreams/$ws/$task-$phase.md"
  else
    rm -f "$state_dir/$task-$phase.md"
  fi
done < <(_psp_phase_list)

# Approval token + trajectory (well-known names, not phases).
if [ -n "$ws" ]; then
  rm -f "$state_dir/workstreams/$ws/$task-approval.token" \
        "$state_dir/workstreams/$ws/$task-trajectory.jsonl"
else
  rm -f "$state_dir/$task-approval.token" "$state_dir/$task-trajectory.jsonl"
fi
```

After the 90-day soak ends and a follow-up pipeline removes legacy-read code paths, Form 2 is dropped — only Form 1 remains.

## Status Reporting

At each phase transition, output a brief status line:

```
[Build] COMPLETE — BUILD_COMPLETE, 5 files changed, 23 tests green
[Review] PARALLEL DISPATCH — code-reviewer + security-engineer spawned...
[Review] COMPLETE — both APPROVE
[Verify] COMPLETE — VERIFIED (3/3 tiers pass)
[Test] COMPLETE — COVERED (87% on critical paths)
[Accept] COMPLETE — APPROVED
[Ship] COMPLETE — PR_CREATED: https://github.com/...
```

## Phase Output

```
Verdict: PIPELINE_COMPLETE / PIPELINE_IN_PROGRESS
Next: Report to user
Artifacts: [PR URL, all phase verdicts, agent summaries]
```

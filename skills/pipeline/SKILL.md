---
name: "pipeline"
description: "Use when user wants to Autonomous pipeline orchestration: classifies work, determines phases, tracks state via tasks, invokes skills in sequence, manages review loops and error recovery. The conductor that replaces manual orchestration. Use at the start of any implementation work."
---

# Pipeline Orchestration

## What This Skill Does

The autonomous conductor for the delivery pipeline. Takes a task, determines which phases apply, and drives skills in sequence — tracking state, managing review loops, and handling failures.

## When to Invoke

- Immediately after classifying work type (feature, refactor, bug fix)
- The `/intake` skill invokes this, or the orchestrator invokes it directly after the pre-flight protocol

## Process

### Step 1: Classify Work and Determine Pipeline

| Work Type | Entry Skill | Pipeline Phases |
|-----------|-------------|-----------------|
| Feature (micro) | `/build-implementation` | Plan → Plan Validation → Build → Review → Ship |
| Feature (small) | `/build-implementation` | Plan → Plan Validation → Build → Review → Verify → Ship |
| Feature (medium) | `/build-implementation` | Plan → Plan Validation → Build → Review → Verify → Test → Accept → Ship → Deploy |
| Feature (large) | `/build-implementation` | Plan → Plan Validation → Build → Review → Verify → Load Test → Test → Accept → Ship → Deploy |
| Refactor | `/refactor` | Plan → Plan Validation → Build → Review → Verify → Test → Accept → Ship |
| Bug Fix | `/bug-fix` | Plan → Plan Validation → Build → Review → Verify → Test → Accept → Ship → Deploy |
| Spike | `/tech-spike` | Spike only (no pipeline) |
| Planning | `/epic-breakdown` | Plan only (produces stories for future pipelines) |

**Pipeline scale tiers:**
- **Micro**: 1 file, less than 5 lines changed, no behavior change → Plan + Plan Validation + Build + Review + Ship
- **Small**: 1-3 files, isolated change → Plan + Plan Validation + Build + Review + Verify + Ship
- **Medium/Large**: Full pipeline. No phase is skipped.

All tiers include Plan + Plan Validation. The `/learn` system may create instincts to adjust this per project/pattern.

### Step 2: Pre-flight Checks (MANDATORY before pipeline state is created)

**Run these checks in order. Each is a hard gate — do not proceed until it passes.**

#### 2-A: CLAUDE.md check
Check for `.claude/CLAUDE.md` or `CLAUDE.md` at the project root.
- **Missing** → invoke `/project-setup` as a blocking subagent (worktree). Wait for `PROJECT_SETUP_COMPLETE` before continuing. Do not ask the user — just run it.
- **Present** → read it and confirm no conflicts with global rules.

#### 2-B: Greenfield check (runs BEFORE architect, BEFORE pipeline state)
Check whether the working directory has no recognizable project file (`package.json`, `Gemfile`, `go.mod`, `pyproject.toml`, `Cargo.toml`, `pom.xml`) AND no `src/`, `app/`, or `lib/` directory.
- **Greenfield detected** → invoke `/greenfield-scaffold` via the Skill tool. **This is a BLOCKING gate.** The pipeline cannot proceed to the architect or any other phase until `/greenfield-scaffold` returns `GREENFIELD_SCAFFOLD_COMPLETE`. The orchestrator must NOT attempt any manual project bootstrap (no `npm init`, no `git init`, no writing `.gitignore` — delegate everything to the greenfield scaffold agent).
- **Not greenfield** → continue.

### Step 2c: Create Pipeline State

**MANDATORY**: Create a structured pipeline state file at pipeline start. This is the single source of truth for pipeline state — it survives context compaction.

The canonical write path is the per-task subdir layout: `pipeline-state/{task-id}/pipeline.md` (workstream variant: `pipeline-state/workstreams/{ws}/{task-id}/pipeline.md`). The legacy flat form `pipeline-state/{task-id}-pipeline.md` is read-tolerated during the 90-day DUAL_PATH soak (see `rules/_detail/pipeline-protocol.md` § Structured Pipeline State) but MUST NOT be written by new pipelines.

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
- Build: pending
- Review: pending
[...other phases per scale...]
- Ship: pending

## Key Files
[list as discovered]
```

Update this file as each phase completes with verdict, artifacts, and agent summaries.

**Mirror the `critical`, `task_class`, and `bestofn` flags from intake.** Read all three from `pipeline-state/{task-id}/intake.md` (set by intake Steps 2d and 2d-bis) and write them into the pipeline state frontmatter on creation. This ensures `/pipeline-resume` preserves the dispatch decision across context compaction so the Build phase still routes correctly.

**Do NOT dual-write to memory/.** The `pipeline-state/` file is the sole authority. Use `/pipeline-resume` to recover state across sessions.

**Discussion context:** If a discussion file exists (`pipeline-state/{task-id}/discussion.md` from intake Step 2b), reference it in the pipeline state under `## Intake Discussion` and pass its decisions to the architect during the Plan phase.

### Workstream Support

If a workstream is active (check `pipeline-state/workstreams/*/workstream.md` for `status: active` entries, or check if the user specified a workstream):
- Create pipeline state in `pipeline-state/workstreams/{workstream}/` instead of `pipeline-state/`
- Use branch convention: `{workstream-branch-prefix}{task-branch}` (e.g., `feat/auth/login-page`)
- Set `CLAUDE_PIPELINE_TASK_ID` to include workstream prefix for trajectory recording

If no workstream is active, use the default `pipeline-state/` directory (existing behavior, no change).

### Step 2a: Multi-Repo Detection (Automatic)

If intake flagged `multi_repo: true`, or if a manifest exists in `~/.claude/manifests/`:

1. **Read or create manifest**: See `rules/_detail/multi-repo-protocol.md` for format and auto-creation triggers
2. **Resolve repo paths**: Verify all manifest repos exist locally. If a planned repo doesn't exist yet, it will be created during scaffold (Step 2b)
3. **Add `manifest:` to pipeline state frontmatter** with the manifest path
4. **Add `## Repos` section** to pipeline state tracking per-repo phases
5. **Determine dispatch mode**: Which repos need build agents? Which need PRs?

If no multi-repo signals → skip this step entirely (single-repo mode, no change to existing behavior).

### Step 2b: Pre-Build Scaffolding (Conditional)

Before the Build phase, check BOTH the task requirements AND the project state. Scaffolding triggers on missing project infrastructure — not just what the task description says. For example, if a CLAUDE.md exists but the project has no Dockerfile, no design system, or no observability, detect and scaffold those automatically.

| Task Signals | Scaffold Skill | What It Produces |
|-------------|---------------|-----------------|
| New API endpoints, REST resource | `/api-scaffold` | Route stubs, controllers, validation, OpenAPI spec |
| Schema change, new table, add column | `/db-migration` | Migration files, index strategy |
| No Dockerfile, no CI/CD, new project | `/infra-scaffold` | Dockerfile, docker-compose, CI/CD pipeline, health endpoints |
| No logging/monitoring configured | `/observability-setup` | Logger config, metrics, tracing, alerting |
| Voice skill/IVR needed | `/voice-scaffold` | Intent model, handler stubs, SSML templates |
| New channel for existing product | `/bff-scaffold` | Channel-specific BFF layer, transformers, gateway route |
| New microservice extraction | `/microservices-scaffold` | Service template, gateway config, tracing. Auto-creates GitHub repo from manifest config |
| Extract module to own repo | `/service-extraction` | New repo via manifest config, code migration, contracts, PRs in both repos |
| New repo needed (from architect plan) | GitHub repo creation | Reads manifest `## Services > GitHub`, creates repo, clones, runs `/project-setup` |
| Empty directory, no project files | `/greenfield-scaffold` | Full project bootstrap: framework, DevX, design system, infra, seed data |
| Frontend feature + no design brief | `/creative-direction` | Design brief: fonts, palette, layout, interaction paradigm |
| Frontend project with no design system | `/design-system-init` | Tokens, Tailwind config, primitive components, dark mode |

Scaffolding is NOT a gate — it produces files and structure that the Build phase then fills with business logic via TDD. Invoke scaffolding skills via the Skill tool (they delegate to the appropriate agent in a worktree).

**Dependency installation is NOT scaffolding.** Adding a package to `package.json` is part of the Build phase, not a pre-build step. Include dependency requirements in the build agent's prompt.

**Detection is automatic.** Check project state directly:

**Greenfield detection (check FIRST, before all other scaffolding):**
If the working directory has no recognizable project file (`package.json`, `Gemfile`, `go.mod`, `pyproject.toml`, `Cargo.toml`, `pom.xml`) AND no `src/` or `app/` or `lib/` directory: this is a greenfield project. Invoke `/greenfield-scaffold` which handles ALL bootstrapping (framework, DevX, design system, infrastructure, seed data). After `/greenfield-scaffold` completes, re-run the scaffold detection table — existing skills will detect any remaining gaps.

- Frontend feature detected (changed files include `.tsx/.jsx/.vue/.svelte`) AND no `pipeline-state/{task-id}/design-brief.md` exists AND no established distinctive branding (tokens.css has only default values or doesn't exist)? → `/creative-direction` FIRST
- No `Dockerfile`? → `/infra-scaffold`
- No `styles/tokens.css` and no `theme.extend.colors` in Tailwind config? → `/design-system-init`
- No logging config and task touches backend? → `/observability-setup`
- Task needs new endpoints but no OpenAPI spec or routes exist? → `/api-scaffold`

**Ordering when multiple scaffolds trigger:** `/creative-direction` → `/design-system-init` → other scaffolds → `/build-implementation`. Creative direction produces the brief; design-system-init consumes it to generate tokens; build uses both.

If the project already has established infrastructure, design system, and patterns, skip scaffolding.

### Step 2c: Cross-Service Checks (Conditional)

If the project CLAUDE.md contains a `## Service Context` section with upstream/downstream services:

1. Read the service context to identify affected contracts
2. If the current change modifies a contract file (OpenAPI spec, Protobuf, event schema): invoke `/cross-service-pipeline` BEFORE the Build phase to verify compatibility and generate a deployment plan
3. After Ship phase, if cross-service deployment is needed: output the deployment plan with service order and flag any manual coordination required

### Step 2d: Plan Validation Gate (ALL pipelines)

After the architect produces a plan, validate it before proceeding to Build.

**Prerequisites**:
- Architect has produced plan output (from `/epic-breakdown` or inline design)
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

1. Write architect's plan to `pipeline-state/{task-id}/plan-validation.md`
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
3. **Parallel phases**: Use Parallel Dispatch Protocol (see `rules/_detail/parallel-dispatch-protocol.md`) — spawn agents in a single message, each reading their own skill file
4. Read the Phase Output (Verdict, Next, Artifacts)
5. If verdict is a failure/rejection: handle per Step 4 (Recovery)
6. If verdict is success: update memory file with verdict and artifacts, advance to next

#### Build Phase Dispatch — Best-of-N Check

Read `bestofn` from the pipeline state frontmatter (mirrored from `pipeline-state/{task-id}/intake.md` at pipeline creation; computed by intake Step 2d-bis as `critical OR (task_class == "feature" AND budget >= 5)`).

- If `bestofn == true`: dispatch via the **Best-of-N Build Team** variant (see `orchestrator/parallel-dispatch-details.md` § Best-of-N Build Team Dispatch). This is not a separate skill — it is a dispatch mode of the Build Team that runs N candidate models in parallel and selects the winner. The winner still proceeds through the normal Review → Final Gate → Ship gates.
- If absent (older pipelines pre-flag): treated as `False` — use standard Build dispatch.
- Otherwise: use the standard Build dispatch (single-engineer subagent with worktree, or standard Build Team for multi-slice / multi-domain work).

**Fallback**: on `BEST_OF_N_FAILED` (e.g. insufficient candidates after env-var validation, or all candidates failed their own tests), automatically fall back to the standard Build dispatch and log the fallback in pipeline state under `## Re-routes` (e.g. `re-routed from best-of-n to standard build (reason: insufficient candidates)`). The pipeline never halts on a Best-of-N failure and never asks the user.

This check fires ONLY at Build dispatch. Scaffolding, Polish, Review, Final Gate, Ship, and Deploy are unaffected.

#### Polish Phase (Conditional: Budget >= 7)

After Build completes and before Review:
1. If Complexity Budget >= 7: invoke `/polish` skill via subagent (Haiku model, worktree)
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
1. Invoke `/design-qc` as part of the Final Gate (parallel with verify + qa + accept)
2. Design QC runs the full DevOps lifecycle: install → build → start server → capture → stop
3. If `CAPTURE_FAILED` → the pipeline **BLOCKS**. Fix the build/server issue before proceeding
4. Screenshots are passed to the product-reviewer for visual validation
5. Product-reviewer MUST receive screenshots — no visual review without them
6. No silent skip — if frontend files changed, visual proof is required

#### Review Phase (TEAM — always)

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
- `Agent({ name: "verifier", team_name: "pipeline-{task-id}", ... })` — `/verify`
- `Agent({ name: "test-analyst", team_name: "pipeline-{task-id}", ... })` — `/qa-test-strategy`
- `Agent({ name: "product-reviewer", team_name: "pipeline-{task-id}", ... })` — `/product-acceptance`
- `Agent({ name: "design-qc", team_name: "pipeline-{task-id}", ... })` — `/design-qc` (if frontend)

All four assess the same final state independently. Shut down after all verdicts collected.

#### Parallel Phases (Dispatch Reference)

- **Review**: teammates in pipeline team (see above)
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
2. Re-run `/qa-test-strategy`

#### Accept APPROVED_WITH_CONDITIONS
1. Spawn engineer to address conditions
2. Re-run `/product-acceptance`

#### Accept REJECTED
1. Return to Build phase with feedback
2. Re-run full pipeline from Build

#### Load Test PERFORMANCE_FAILED
1. Identify bottlenecks (database queries, missing indexes, no caching)
2. Return to Build phase to optimize
3. Re-run `/load-test`

#### Deploy DEPLOY_FAILED or AUTO_ROLLBACK
1. `/deployment-verification` triggered automatic rollback
2. Investigate failure cause from verification report
3. Create bug fix via `/intake`, re-enter pipeline

#### PR_BLOCKED
1. Fix quality gate failures
2. Re-run `/pr-creation`

### WRONG_SKILL Handling

When a skill returns `WRONG_SKILL: {guidance}`, the orchestrator automatically re-invokes the correct skill with the same task context. No user prompt. The re-invocation is logged to pipeline state as `re-routed from /{original-skill} to /{target-skill} (reason: {guidance})`.

- **Maximum one re-route per pipeline** — a second `WRONG_SKILL` escalates to user.
- The target skill is parsed from the guidance text (e.g., `WRONG_SKILL: use /module-extraction` → target is `/module-extraction`).
- Routing is recorded in `pipeline-state/{task-id}/pipeline.md` under a `## Re-routes` section.

### Step 4b: Extraction Assessment (Automatic, Post-Accept)

After Accept phase completes (APPROVED), check whether the codebase has grown to warrant service extraction:

1. Check the code-reviewer's output for **Extraction Candidate** flags (from the Review phase)
2. If extraction candidates were flagged with 3+ signals:
   - Report to user: "[Module] has crossed extraction thresholds. Recommend running `/service-extraction` after this feature ships."
   - If the user has previously configured auto-extraction (via `CLAUDE_AUTO_EXTRACT=true` in settings.json env), invoke `/service-extraction` automatically after Ship phase
   - Otherwise: add to pipeline output as a recommended follow-up action

This assessment is zero-cost — it reads the existing review output. No additional analysis needed.

### Step 4c: Multi-Repo Ship (Automatic When Manifest Exists)

When the pipeline has a manifest (multi-repo mode):

1. **Create PRs per repo** in dependency order (providers first):
   - For each repo with changes, run `/pr-creation` in that repo's working directory
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

1. Check PR merge status: `gh pr view [PR_NUMBER] --json state -q '.state'`
2. If `MERGED`: automatically invoke `/deploy` → `/deployment-verification`
3. If `OPEN`: inform user PR is ready for review. The deploy phase will run when the user returns after merge — `/pipeline-resume` detects Ship=completed + Deploy=pending and auto-continues.

For micro/small pipelines: deploy is optional (inform user, don't auto-invoke).

#### Multi-Service Deploy (When Manifest Exists)

When the pipeline has a manifest with multiple repos and deploy targets:

1. Read `## Deploy Order` from manifest
2. Deploy in dependency order: providers first, then consumers
3. After each service deploys: run health check, verify `/deployment-verification`
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
4. Clean up pipeline-state file (see Step 7d for the canonical Reflect cleanup snippet — dual-form during the DUAL_PATH soak)

### Step 7: Reflect

**MANDATORY** after every pipeline. Three sub-steps, in order:

#### 7a. Pipeline Analytics (before cleanup)

Capture quantitative pipeline metrics before state files are deleted:
```bash
bash ~/.claude/hooks/pipeline-analytics.sh {task-id}
```
This aggregates phase verdicts, agent counts, and review rounds into `metrics/pipelines.jsonl`. Must run before state file cleanup in Step 6.

#### 7b. Qualitative Reflection

Run the reflection checklist from `rules/_detail/reflection-protocol.md`.

If the pipeline experienced failures, >2 review rounds, or any recovery loop: invoke `/forensics` before reflection. The forensics report provides evidence-based findings for the reflection checklist.

1. Review the pipeline execution for issues, surprises, and validated patterns
2. Identify improvements to rules, project CLAUDE.md, global CLAUDE.md, agent definitions, skills, or memory
3. Apply identified changes (delegate source file changes to agents)

#### 7c. Learning Extraction (automatic)

Invoke `/learn` to analyze session observations, pipeline analytics, and review findings. This:
1. Reads enriched observations for this session (tool usage with phase, role, outcome)
2. Reads pipeline analytics for this project (last N pipelines from `metrics/pipelines.jsonl`)
3. Reads review findings from the current pipeline's review state file (if it exists, before cleanup)
4. Detects patterns and creates/updates instinct files in `learning/instincts/`
5. Classifies review findings as "preventable by build agent" vs. "review-level only"
6. Converts preventable findings into build-targeted instincts (backward feedback loop)
7. Reports new/updated instincts to the orchestrator

The orchestrator reports learnings to the user (skip if nothing actionable). Every pipeline — whether it had rework or ran clean — feeds the learning flywheel.

#### 7d. Reflect Cleanup (Dual-Form During DUAL_PATH Soak)

After analytics, reflection, and learning are complete, remove the pipeline state files. Cleanup is dual-form during the 90-day DUAL_PATH soak (per `rules/_detail/pipeline-protocol.md` § Structured Pipeline State):

1. **Form 1 — new-layout subdir cleanup**: empty the per-task subdir with `find -delete` (sandbox-safe — `rm -rf` on directories is denied by the sandbox even on orchestrator-writable paths). Workstream variant: same pattern under `pipeline-state/workstreams/{ws}/{task-id}/`.
2. **Form 2 — legacy phase enumeration**: iterate the canonical phase list via `_psp_phase_list` (sourced from `hooks/_lib/pipeline-state-paths.sh`) and remove each `pipeline-state/{task-id}-{phase}.md` file. **NEVER use a bare wildcard glob over the task prefix** — that matches prefix neighbours (e.g. cleanup of `tool` would delete `tool-timing-capture-*` files). R12 mitigation.
3. Approval token + trajectory have well-known names; remove them by exact path: `pipeline-state/{task-id}-approval.token` and `pipeline-state/{task-id}-trajectory.jsonl`.

Canonical cleanup snippet (mirrors what the orchestrator runs):

```bash
source ~/.claude/hooks/_lib/pipeline-state-paths.sh
state_dir="$HOME/.claude/pipeline-state"
task="{task-id}"
ws=""  # set to the workstream name when applicable

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

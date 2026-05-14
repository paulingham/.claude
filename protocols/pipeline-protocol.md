# Pipeline Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/pipeline-orchestration.md`

## Skills Are Mandatory, Not Optional

When a pipeline phase has a corresponding skill, the skill's procedure MUST be executed. The dispatch mechanism depends on the phase:

- **Subagent phases** (Plan, Ship, Deploy, single-slice Build): Invoke via Skill tool or Agent tool with `isolation: "worktree"`. Ephemeral, no visibility.
- **Team phases** (multi-slice Build, Review, Final Gate): Spawn teammates into the pipeline team via Agent tool with `team_name`. Visible in tmux panes. See `rules/parallel-dispatch-protocol.md`.
- **Single-slice Build**: Use subagent with `isolation: "worktree"` (team overhead not justified for one engineer).

**The skill IS the phase.** Whether invoked via Skill tool, read by a subagent, or read by a teammate, the full skill procedure must be followed.

### Team Dispatch

For phases in the Team Phases table (see `rules/parallel-dispatch-protocol.md`), teammates are spawned into the pipeline team and read their own skill files. The orchestrator creates tasks and assigns them. See `orchestrator/parallel-dispatch-details.md` for exact dispatch procedure.

## Best-of-N Build Dispatch (overview)

Best-of-N Build dispatch fires when `/intake` tags the task with `bestofn: true` (`critical OR user_override`). N candidate engineers run in parallel worktrees, each on a different model; a single code-reviewer selects the winner. The winner still faces the normal Review → Final Gate → Ship gates. Cost is roughly 2-3x a standard build. The full procedure (pre-flight resource check, candidate roster, scoring rubric, merge & cleanup, fallback) lives in `~/.claude/orchestrator/parallel-dispatch-details.md` § Best-of-N Build Team Dispatch.

## Build Phase Dispatch Variants

The Build phase has three dispatch variants. Routing precedence is `pdr_rtv > bestofn > standard` — when multiple flags fire on the same slice, the strictly stronger variant wins. Both `pdr_rtv` and `bestofn` are computed by `/intake` Step 2d / 2d-bis and persisted to `pipeline-state/{task-id}/intake.md` frontmatter; `/pipeline` Step 3 reads them at Build dispatch time.

| Flag combination | Dispatch | Why |
|---|---|---|
| `pdr_rtv == true AND bestofn == true` | **PDR-RTV wins** (strictly stronger). Logged as a re-route. | PDR-RTV's T=2 iterations + summary-based tournament dominates Best-of-N's T=1 + code-reviewer rubric on the same parallel-build budget. |
| `pdr_rtv == true AND bestofn == false` | PDR-RTV. | Triggered by `budget >= ${CLAUDE_PDR_RTV_BUDGET_FLOOR:-10} AND critical`. |
| `pdr_rtv == false AND bestofn == true` | Best-of-N (existing path, unchanged). | Triggered by `critical OR user_override`. |
| `pdr_rtv == false AND bestofn == false` | Standard Build (single engineer, or multi-slice parallel engineers). | Default. |

**Fallback semantics**: PDR-RTV emits `PDR_NO_CONSENSUS` when (a) <4 candidates produce green builds across both iterations, OR (b) tournament verifier rejects every finalist, OR (c) worktree-cap exceeded at pre-flight. The pipeline silently re-routes to Best-of-N → standard; the fallback is logged in pipeline state's `## Re-routes` section with a `fallback_reason` enum (`worktree-cap-exceeded` | `insufficient-green-builds` | `all-finalists-rejected`). Best-of-N's existing `BoN_FALLBACK_TO_SINGLE` chain remains in place under it. Worst case is single-engineer Build — the same floor the harness already accepts.

The full PDR-RTV procedure lives in `~/.claude/orchestrator/parallel-dispatch-details.md` § PDR-RTV Build Team Dispatch.

## Structured Pipeline State

Phase results are persisted as files in `~/.claude/pipeline-state/` to survive context compaction and enable inter-phase communication.

### File Convention (Canonical — per-task subdirectory)

The canonical layout is **per-task subdirectory**: every artifact for a given pipeline lives under `pipeline-state/{task-id}/`.

- **Naming**: `pipeline-state/{task-id}/{phase}.md` (e.g. `pipeline-state/auth-feature/build.md`, `pipeline-state/PROJ-123/review.md`)
- **Workstream variant**: `pipeline-state/workstreams/{ws}/{task-id}/{phase}.md` (workstream-scoped pipelines nest under `workstreams/{ws}/`)
- **Scratchpad**: `pipeline-state/{task-id}/scratchpad/{role}-{phase}.md` (workstream variant: `pipeline-state/workstreams/{ws}/{task-id}/scratchpad/{role}-{phase}.md`)
- **Approval token**: `pipeline-state/{task-id}/approval.token`
- **Trajectory**: `pipeline-state/{task-id}/trajectory.jsonl`
- **Health reports** (project-wide, NOT task-keyed): `pipeline-state/health-reports/{date}.md`
- **Lifecycle**: created by phase agent/skill, read by next phase, emptied via `find {task-id} -type f -delete && find {task-id} -depth -type d -empty -delete` after pipeline completes (`rm -rf` on directories is sandbox-denied even on orchestrator-writable paths — see `skills/pipeline/SKILL.md` Step 7d for the canonical snippet) AND any `refs/checkpoints/{task-id}/*` refs in the shared ref database (created by `hooks/shadow-git-checkpoint.sh`) deleted via the canonical Step 7d pre-step
- **Why files, not memory**: files survive context compaction intact; orchestrator memory does not
- **Why subdirectory**: cleanup is bounded to one task-prefix (no prefix-collision risk — `tool` cleanup cannot match `tool-timing-capture-*`); concurrent pipelines are filesystem-isolated

### DUAL_PATH soak (90-day window)

The harness is migrating from a flat layout (`pipeline-state/{task-id}-{phase}.md`) to the canonical subdirectory layout above. **DUAL_PATH** is the migration strategy: readers tolerate both layouts, writers go to NEW layout only. The soak runs for **90 days** from the migration PR's merge timestamp (aligned with `CLAUDE_LEARNING_RETENTION_DAYS` precedent), after which a follow-up pipeline removes the legacy-read code paths.

During the soak:

- **Writers always emit the new layout**. No skill or hook writes to the legacy form.
- **Readers tolerate both layouts**. Discovery globs cover both forms; helper functions in `hooks/_lib/pipeline_state_paths.py` (Python) and `hooks/_lib/pipeline-state-paths.sh` (bash) are the single point of truth for path resolution.
- **Discovery globs (canonical)**:
  ```
  pipeline-state/<task>/pipeline.md                            # new, root
  pipeline-state/workstreams/<ws>/<task>/pipeline.md           # new, workstream
  pipeline-state/<task>-pipeline.md                             # legacy, root
  pipeline-state/workstreams/<ws>/<task>-pipeline.md            # legacy, workstream
  pipeline-state/health-reports/                                # EXCLUDED from active-pipeline scans
  ```
- **Read-precedence (locked by tests)**: workstream layout beats root layout when `task_id` collides. Within a single layout-class, fresher mtime wins. Ties favour the new layout. The approval-token reader returns whichever path exists; if both exist, fresher mtime wins.
- **Reflect cleanup is dual-form**: `find pipeline-state/{task-id} -type f -delete && find pipeline-state/{task-id} -depth -type d -empty -delete` for the new layout (NOT `rm -rf` — sandbox-denied on directories) AND iterate the canonical phase list (`_psp_phase_list`) to remove any legacy `pipeline-state/{task-id}-{phase}.md` files. Bare globs are forbidden (they would catch prefix neighbours). Reflect cleanup ALSO deletes shadow checkpoint refs via `git for-each-ref refs/checkpoints/{task-id}/` + per-ref `update-ref -d`, run BEFORE Form-1 file deletion per `skills/pipeline/SKILL.md` Step 7d.
- **Soak end**: a cleanup pipeline removes legacy-read code paths from helpers, hooks, and skills, gated on `find pipeline-state -maxdepth 1 -name "*-pipeline.md" -type f` returning zero.

### Format
```markdown
---
task_id: {task-id}
phase: {plan|build|review|verify|test|accept|ship}
verdict: {BUILD_COMPLETE|APPROVE|VERIFIED|COVERED|APPROVED|PR_CREATED|etc}
timestamp: {ISO 8601}
---

## Summary
{1-3 sentence phase outcome}

## Test Results
- Passed: {N}
- Failed: {N}
- Coverage: {N}%

## Key Findings
- {finding 1}
- {finding 2}

## Next Phase Input
{What the next phase needs to know from this phase}
```

### Orchestrator Responsibilities
- Check `pipeline-state/` for in-progress work before starting any new pipeline (use `_psp_find_active_pipelines` or `find_pipeline_files` — they cover both layouts)
- If in-progress state found: invoke `/pipeline-resume` to continue from the correct phase
- `pipeline-state/` is the single source of truth — do NOT dual-write to `memory/`
- Pass the previous phase's state file path to the next phase agent
- Delete all state files for a task after pipeline completion or abandonment
- At Reflect step 6d, empty `pipeline-state/{task-id}/` via `find -delete` (new layout — `rm -rf` is sandbox-denied) AND iterate `_psp_phase_list` to remove legacy `pipeline-state/{task-id}-{phase}.md` + `pipeline-state/{task-id}-approval.token` files. Stale APPROVED tokens from crashed pipelines would silently pre-authorize future pipelines that reuse the same task-id.
- Never leave stale state files — they confuse future pipeline runs
- Never use bare globs (`pipeline-state/{task-id}*`) for cleanup — prefix neighbours collide. Always enumerate phases via `_psp_phase_list`.

## Phase Checklist (Summary)

Before advancing to any phase, verify the previous gate passed AND invoke the required skill.

- **Plan**: Design validation is a HARD GATE (ALL pipelines). No implementation begins without:
  1. Architect produces plan with one chosen approach + a one-line "rejected: X because Y" note for any obvious alternative they considered. **Full `## Alternatives Considered` table is required ONLY for**: (a) interactive mode, (b) `critical == true`, (c) `Budget >= 7`. In autonomous low-budget runs, the architect evaluates alternatives internally and writes only the chosen approach plus the brief rejection note. The visible alternatives table existed primarily for human consensus-building; AI architects can reason through alternatives without rendering them in the plan file every time.
  2. Interactive mode: user approves the plan.
  3. Autonomous mode dispatch (chosen by criticality + budget):
     - **Heavy** (`critical == true OR Budget >= 7`): full alternatives table required (per step 1). Spawn product-reviewer + software-engineer challengers — both must APPROVE the plan. Maximum 2 rounds of revision before escalation.
     - **Light** (everything else): invoke `/plan-self-validation` — architect re-reads its own plan against a structured holes-finding rubric. One-shot, no team. The rubric explicitly asks "did the architect miss an obvious alternative for this pattern?" so plan quality is checked even when the alternatives table is absent. Verdict: `PLAN_APPROVED` continues; `PLAN_HOLES` returns to architect with the hole list (max 1 revision; if still holes, escalate to heavy challengers).
  4. Gate tracked in pipeline state as `Plan Validation` phase. Pipeline state records the dispatch mode (`heavy` or `light`) for forensic visibility.
  Use `/epic-breakdown`, `/estimation`, `/story-writing`, `/tech-spike` as needed
- **Build**: `/build-implementation` or `/refactor` or `/bug-fix` — ATDD, shape self-check, **then `/code-review` as Step 5 AND `/sandbox-verify` as Step 5b — both inline gates inside Build**. Code-review is no longer a separate phase boundary; sandbox-verify is the second inline gate that confirms the worktree's pass set reproduces in a fresh E2B sandbox. CHANGES_REQUESTED (Step 5) and SANDBOX_FAILED (Step 5b) both dispatch fix-engineer in-line with a single 2-round cap **combined across Step 5 and Step 5b** (NOT 2+2). Build's `BUILD_COMPLETE` verdict requires ATDD audit trail AND code-reviewer APPROVE AND sandbox-verify SANDBOX_VERIFIED or SANDBOX_SKIPPED.
- **Review (Security)**: `/security-review` — security audit with own gate (different concern from code quality, justifies own phase). Must APPROVE.
- **Final Gate** (Verify + Test + Accept + Patch Critique as team, parallel):
  - `/verify` -- check E2E trigger matrix (`rules/e2e-protocol.md`) AND the External Oracle tier (Tier 5, `skills/verify/SKILL.md` § 4.75). When a known-good external comparator exists for the change (reference parser, upstream SQL engine, schema validator, reference implementation — GCC-as-oracle pattern), oracle-match is required for `VERIFIED`; emit `VERIFIED_WITH_SKIP` when the oracle applies but cannot execute, and N/A (no verdict impact) when no oracle applies.
  - `/qa-test-strategy` -- all ACs covered, no gaps
  - `/product-acceptance` -- APPROVED required
  - `/patch-critique` -- PATCH_APPROVED required (rubric: tests cover change, diff minimal vs spec, no obvious regressions, no incidental refactor). PATCH_REJECTED returns to fix-engineer (no user escalation per § In-Cycle Fix Rule).
- **Ship**: `/pr-creation` -- PR with narrative, quality gate passes. Requires `pipeline-state/{task-id}-approval.token` with verdict `APPROVED` or `APPROVED_WITH_CONDITIONS` (written by `/product-acceptance`). Gate checked at `/pr-creation` Step 0 via `hooks/_lib/approval-token.sh`. Missing or REJECTED token → `PR_BLOCKED`.

#### `gh pr create` Bypass (Residual Risk, Out of Scope)

Direct `gh pr create` invocations via Bash bypass the `/pr-creation` skill and therefore bypass the approval token gate. The existing `main-branch-guard.sh` PreToolUse hook already enforces the worktree pattern for `gh pr create`, but does not check the approval token. A future `hooks/pr-approval-guard.sh` hook could extend coverage to direct Bash invocations — tracked as a follow-up, not in this wave.

## Review Protocol

### Code Review (inside Build phase)
Code-review runs as the final step of `/build-implementation` — see the build-implementation skill for the inline dispatch. Build does not emit `BUILD_COMPLETE` until code-reviewer APPROVES. CHANGES_REQUESTED inside Build spawns fix-engineer, re-runs the suite, and re-dispatches code-reviewer with the original finding + fix diff (max 2 rounds, then escalate).

### Security Review (separate phase)
After Build emits `BUILD_COMPLETE`, dispatch `/security-review` as its own phase. Security review uses a separate gate from code review because the concern is orthogonal — a security finding is not "another category of code quality issue".

Both reviewers use the same severity threshold: CRITICAL, HIGH, or MEDIUM findings trigger CHANGES_REQUESTED. LOW and INFO findings are included in the review output for the PR narrative but do not gate advancement.

### In-Cycle Fix Rule (IRON LAW)

> **Findings surfaced during review are fixed IN THIS PIPELINE. Never filed as follow-ups. Never surfaced as questions to the user.**

This applies to findings from code-reviewer, security-engineer, product-reviewer, qa-engineer, verify phase, AND build-phase scratchpad warnings that indicate the shipped change is incomplete or leaves adjacent documented behavior broken.

The orchestrator dispatches a dedicated `fix-engineer` (see `agents/fix-engineer.md`) on every CHANGES_REQUESTED, GAPS_FOUND, REJECTED, PATCH_REJECTED, or UNVERIFIED return. fix-engineer reuses the prior build's worktree (NOT a fresh one) and operates with fix-cycle-specific guidance: verify finding validity first, no scope creep, no compliance commit messages, no source-code apology comments.

- **No follow-up tickets** for defects the current change exposes, leaves broken, or makes misleading. Follow-ups are ONLY for genuinely orthogonal work (different module, different contract, different user journey).
- **No "ship as-is + file ticket"** compromises. The pipeline does not ship known-incomplete fixes.
- **No questions to the user** asking whether to expand scope. The pipeline decides autonomously: dispatch fix-engineer, roll the fix into the current branch family, re-run targeted review, then ship.
- **"Minimal scope" / "narrow fix" user directives** constrain *approach* (don't reorganize, don't refactor unrelated code), not *coverage* (ignore defects the fix exposes). Read user constraints literally.
- **Escalate to the user ONLY if** the required fix is architecturally large (cross-service, new module, >~100 LOC) OR outside the current task's layer. In that case HALT the pipeline — do not ship the incomplete fix.

Round counting: expanding scope to fix an in-cycle finding does NOT reset the review-round counter, but a clean re-review on the combined diff is still required before ship.

### After CHANGES_REQUESTED (orchestrator dispatch)

The orchestrator-side procedure (spawn fix-engineer into the team, merge fix branch, re-assign the raising reviewer with the targeted finding + diff, max 2 rounds) lives in `~/.claude/orchestrator/pipeline-orchestration.md` § After CHANGES_REQUESTED. Agents reading this file only need to know: the raising reviewer is re-dispatched with the original finding + fix diff and re-reviews only the addressed findings plus immediate surrounding context.

### Fix Agent Review-Receiving Protocol

When spawning an engineer to address review findings, the prompt MUST include:

1. **Verify before implementing**: The fix agent must verify the reviewer's finding is valid before changing code. Read the cited code, understand the context, check if the concern applies.
2. **Technical correctness over compliance**: If the reviewer's suggestion would make the code worse, the fix agent reports back with a technical justification — it does not blindly implement.
3. **Actions over explanations**: Fix the code. Do not add comments explaining why the old code was wrong. The diff speaks.
4. **No compliance phrases in commits**: "Fixed per review feedback" is not a commit message. Describe WHAT changed and WHY.

### Why Single Re-Review
The build agent self-reviews before completion. Hooks enforce shape compliance. Tests prove correctness. A fix to a specific finding should not require a full re-audit — that is the assembly-line anti-pattern.

### Review Rules

1. **Never trust a fix agent's self-report.** Re-dispatch the raising reviewer independently after fix.
2. **Re-dispatch via Parallel Dispatch Protocol.** Each agent reads its own skill file. Do not paraphrase.
3. **Disputed findings require resolution, not dismissal.** The orchestrator cannot unilaterally dismiss.
4. **Track the loop.** Record verdicts, findings, fix plans, and re-review results.
5. **Maximum 2 total rounds.** Escalate to user if not resolved after 1 re-review.

## Environment-Dependent Debugging Loop

When a built feature passes unit tests but fails in a real environment (device, staging, browser, external system), the pipeline enters a debugging loop:

### Persistent State
When entering the debugging loop, invoke `/debug` to create persistent state in `pipeline-state/{task-id}-debug.md`. This ensures hypotheses, elimination results, and fix attempts survive context compaction and session boundaries.

### Entry criteria
- Feature was built and tests pass
- User reports failure with environment evidence (screenshot, logs, DOM dump, error output)
- The failure cannot be reproduced by unit tests alone

### Loop procedure
1. User reports failure with evidence
2. Orchestrator spawns agent (worktree) to fix the specific issue
3. Merge fix, push, user tests in environment
4. Repeat until user confirms working
5. Resume pipeline from **Review** phase on the cumulative diff

### Rules during the loop
- Pipeline gates (review, verify, test, accept) are **SUSPENDED** — they run once on the final working state
- Each fix still goes through an **agent** (orchestrator NEVER edits source files directly)
- Each fix is **committed** with a descriptive message (audit trail preserved)
- Maximum **5 iterations** — then escalate to user with options
- The orchestrator coordinates and delegates, it does not write code — especially under time pressure

### Why this exists
Environment-dependent testing (mobile devices, WebView integration, staging deploys) inherently requires test-fix-retest cycles that unit tests cannot validate. Running full pipeline gates on each intermediate fix wastes effort on throwaway states. The gates add value on the final working state, not on each debugging step.

## Enforcement

> **IRON LAW: NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED.**

The orchestrator self-discipline checks ("if you catch yourself...") live in `~/.claude/orchestrator/pipeline-orchestration.md` § Enforcement. The iron law itself is mirrored in `rules/core.md` and applies to every spawn.

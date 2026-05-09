# Parallel Dispatch Details (Orchestrator-Only)

Extracted from `rules/_detail/parallel-dispatch-protocol.md`. Agents do not need this content.

## Team Creation

At pipeline start, create the team:

```
TeamCreate({
  team_name: "pipeline-{task-id}",
  description: "Pipeline for {feature name}"
})
```

One team per pipeline. All phase teammates join this team. The shared task list at `~/.claude/tasks/pipeline-{task-id}/` tracks all work.

## Team Dispatch

Every teammate spawn propagates `CLAUDE_SUBAGENT_DEPTH` through the spawn
shell so `hooks/depth-guard.sh` can refuse runaway recursion. Set
`CLAUDE_SUBAGENT_DEPTH = parent_depth + 1` in the shell that invokes the
Agent tool — the teammate inherits it via process env. See
`rules/_detail/agent-protocol.md > Resource Bounds` for caps and override semantics.

Example (orchestrator-side teammate spawn shell):

```bash
parent_depth="${CLAUDE_SUBAGENT_DEPTH:-0}"
child_depth=$((parent_depth + 1))
CLAUDE_SUBAGENT_DEPTH=$child_depth Agent \
  --subagent_type=code-reviewer \
  --team_name=pipeline-{task-id} \
  --name=reviewer-1 \
  --prompt="..."
```

The literal `CLAUDE_SUBAGENT_DEPTH=<N>` assignment must appear in the spawn
shell — not just in surrounding prose. The runtime-guard hook (`hooks/runtime-guard.sh`)
records the teammate's start time at this same call and emits a precise
`SendMessage({type:"shutdown_request", name:"<display>"})` directive on
stderr if the teammate later exceeds `CLAUDE_TEAMMATE_MAX_RUNTIME` (3600s
default). Subagent-class spawns (`team_name` empty) get a next-tool-call-blocked
directive — see `rules/_detail/parallel-dispatch-protocol.md > Resource Bounds`
for the Path-B disclosure.

## Plan Phase Dispatch

Plan phase has two stages when the heavy plan-validation gate applies (`critical == true OR Budget >= 7`). Below the heavy threshold, skip Stage 1 (recon) — the overhead is not justified for small tasks — and dispatch only Stage 2 (architect).

### Stage 1: Pre-Architect Recon (heavy gate only)

Three recon agents run in parallel to seed the architect with hindsight. Each writes its output to a separate file; the orchestrator concatenates them into `pipeline-state/{task-id}/architect-context.md` before architect dispatch.

Spawn all three in a single message:

```
parent_depth="${CLAUDE_SUBAGENT_DEPTH:-0}"
child_depth=$((parent_depth + 1))

CLAUDE_SUBAGENT_DEPTH=$child_depth Agent({
  subagent_type: "architect-context-recon",
  prompt: "You are operating in **code-archaeology** mode. Read ~/.claude/agents/architect-context-recon.md § 'Mode 1: code-archaeology' for your full procedure.

    ## Spawn inputs
    - Task ID: {task-id}
    - Acceptance criteria: see TaskList for details
    - outputPath: pipeline-state/{task-id}/architect-context-archaeology.md

    Write your findings to outputPath, then emit RECON_COMPLETE or RECON_NULL on stdout."
})

CLAUDE_SUBAGENT_DEPTH=$child_depth Agent({
  subagent_type: "architect-context-recon",
  prompt: "You are operating in **memory-mining** mode. Read ~/.claude/agents/architect-context-recon.md § 'Mode 2: memory-mining' for your full procedure.

    ## Spawn inputs
    - Task ID: {task-id}
    - Acceptance criteria: see TaskList for details
    - Project hash: {project-hash}
    - outputPath: pipeline-state/{task-id}/architect-context-memory.md

    Write your findings to outputPath, then emit RECON_COMPLETE or RECON_NULL on stdout."
})

CLAUDE_SUBAGENT_DEPTH=$child_depth Agent({
  subagent_type: "architect-context-recon",
  prompt: "You are operating in **domain-analysis** mode. Read ~/.claude/agents/architect-context-recon.md § 'Mode 3: domain-analysis' for your full procedure.

    ## Spawn inputs
    - Task ID: {task-id}
    - Acceptance criteria: see TaskList for details
    - outputPath: pipeline-state/{task-id}/architect-context-domain.md

    Write your findings to outputPath, then emit RECON_COMPLETE or RECON_NULL on stdout."
})
```

After all three return, the orchestrator concatenates:

```bash
cat pipeline-state/{task-id}/architect-context-archaeology.md \
    pipeline-state/{task-id}/architect-context-memory.md \
    pipeline-state/{task-id}/architect-context-domain.md \
    > pipeline-state/{task-id}/architect-context.md
```

The three intermediate files are kept for forensic visibility (deleted by Reflect cleanup along with the rest of `pipeline-state/{task-id}/`).

`RECON_NULL` from any agent is non-blocking — the agent still wrote a valid file (anti-findings only). Concatenation proceeds normally and the architect sees the gap.

If a recon agent fails (no file written, no verdict emitted), retry once. If it fails twice, proceed to Stage 2 without that mode's findings — recon is advisory; the architect's cold-start fallback path already handles missing context.

### Stage 2: Architect Dispatch

```
parent_depth="${CLAUDE_SUBAGENT_DEPTH:-0}"
child_depth=$((parent_depth + 1))
CLAUDE_SUBAGENT_DEPTH=$child_depth Agent({
  subagent_type: "architect",
  prompt: "Read ~/.claude/agents/architect.md for your full role definition, including the Pre-Drafting Recon, Pre-Emit Self-Review, and Plan Output Contract sections.

    ## Spawn inputs
    - Task ID: {task-id}
    - Acceptance criteria: see TaskList for details
    - Architect context (recon, heavy gate only): pipeline-state/{task-id}/architect-context.md (Read this BEFORE drafting if it exists)
    - Project CLAUDE.md: read for tech stack and conventions

    ## Output
    Write the plan to pipeline-state/{task-id}/plan.md per the Plan Output Contract (4 artifacts + Pre-Emit Self-Review)."
})
```

When recon ran, the architect's plan citations should reflect the recon findings — codebase precedents, fragile areas, prior challenger findings the architect now knows about. The Plan Validation challengers will detect a hollow `architect-context.md` (architect did not Read it) by checking whether plan citations align with recon findings; misalignment is a HIGH finding on Artifact 2.

## Plan Validation Phase Dispatch (Autonomous Mode)

Spawn both challengers in a single message:

```
// Step 1: Create tasks
TaskCreate({ title: "Plan review: product perspective", description: "Challenge scope, value, AC quality" })
TaskCreate({ title: "Plan review: engineering feasibility", description: "Challenge verticality, feasibility, error paths" })

// Step 2: Spawn challengers
Agent({
  name: "plan-reviewer",
  team_name: "pipeline-{task-id}",
  subagent_type: "product-reviewer",
  prompt: "You are operating in **Plan Validation Mode (Challenger)** — reviewing a plan BEFORE implementation begins. There is no code yet. You are challenging the architect's design decisions.

    Read ~/.claude/agents/product-reviewer.md and follow the **'Plan Validation Mode (Challenger)'** section as your full grading rubric. Do NOT apply the post-build Acceptance Review rubric — that is the wrong mode for this phase.

    ## Inputs
    - Plan file: pipeline-state/{task-id}/plan.md (Read this; do not assume the prompt contains the full plan)
    - Original story / acceptance criteria: see TaskList for details
    - Architect-context (recon): pipeline-state/{task-id}/architect-context.md (if it exists)

    ## Grading Surface (per agents/architect.md § Plan Output Contract)

    The plan must contain four artifacts. Grade each:
    1. Failing test stubs per AC
    2. Codebase ground-truth citations
    3. Pre-mortem (3 named failure modes)
    4. User-proxy walkthrough

    Plus a Pre-Emit Self-Review section with three personas answered. Persona 2 (PM Who Shipped a Feature That Flopped) is your responsibility to verify — missing or generic answers = HIGH finding.

    ## Findings & Verdict

    Severity: HIGH / MEDIUM / LOW per finding.

    Verdict (per your agent file's rubric):
    - APPROVE: all artifacts complete, ≤2 LOW findings.
    - CHANGES_REQUESTED: ≥1 HIGH OR ≥3 MEDIUM findings.

    Output structure: verdict line, then findings grouped by severity, each citing the artifact (or self-review persona) it applies to."
})

Agent({
  name: "plan-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "software-engineer",
  prompt: "You are operating in **Plan Validation Mode (Challenger)** — reviewing a plan BEFORE implementation begins. There is no code yet. Do NOT create files or write code.

    Read ~/.claude/agents/software-engineer.md and follow the **'Plan Validation Mode (Challenger)'** section as your full grading rubric. Do NOT apply the build-mode TDD/implementation flow — that is the wrong mode for this phase.

    Read the project CLAUDE.md for tech stack and conventions.

    ## Inputs
    - Plan file: pipeline-state/{task-id}/plan.md (Read this; do not assume the prompt contains the full plan)
    - Original story / acceptance criteria: see TaskList for details
    - Architect-context (recon): pipeline-state/{task-id}/architect-context.md (if it exists)
    - The actual codebase (use Read/Grep to verify the architect's citations)

    ## Grading Surface (per agents/architect.md § Plan Output Contract)

    The plan must contain four artifacts. Highest-leverage check: **verify codebase ground-truth citations by Reading the cited files yourself**. Architect-claimed citations that don't match the actual code are HIGH findings.

    Plus a Pre-Emit Self-Review section with three personas answered. Personas 1 (Staff Engineer Who's Seen It Fail) and 3 (Future-You at 2am) are your responsibility — missing or surface-level = HIGH finding.

    ## Engineering Concerns Specific to Plan Phase
    Apply the checks listed in your agent file: slice independence, test mix per slice, dependency justifications, OUT-OF-SCOPE clarity, rollback plans for data changes.

    ## Findings & Verdict

    Severity: HIGH / MEDIUM / LOW per finding.

    Verdict (per your agent file's rubric):
    - APPROVE: citations verified, slices sound, scope clear; ≤2 LOW findings.
    - CHANGES_REQUESTED: ≥1 HIGH OR ≥3 MEDIUM findings.

    Output structure: verdict line, then findings grouped by severity, each citing the artifact (or self-review persona) it applies to."
})
```

On CHANGES_REQUESTED:
```
// 1. Re-spawn architect with combined feedback
Agent({
  subagent_type: "architect",
  prompt: "Read ~/.claude/agents/architect.md and ~/.claude/skills/epic-breakdown/SKILL.md.
    Your previous plan was challenged in Plan Validation. Revise based on this feedback.

    Original plan: pipeline-state/{task-id}/plan.md (read it)

    Challenger feedback (HIGH/MEDIUM/LOW findings from plan-reviewer + plan-engineer):
    {combined_feedback}

    Requirements:
    - Address every HIGH and MEDIUM finding. Either fix the artifact, or answer the finding inline with rationale (and update artifact accordingly).
    - Re-run the Pre-Emit Self-Review section if any persona's answer changed substantively.
    - Re-verify any Codebase Ground-Truth Citations the engineering challenger flagged — Read the cited file/lines, correct the claim or mark `<unverified>`.
    - Do not make unrelated changes to approved aspects.
    - Output the revised plan to pipeline-state/{task-id}/plan.md (overwrite)."
})

// 2. Re-submit to SAME challengers (still alive, have context)
// Only message the rejecting challenger(s) -- targeted re-review
SendMessage({
  to: "plan-reviewer",  // only if this challenger rejected
  message: "The architect has revised the plan based on your feedback.
    Revised plan: pipeline-state/{task-id}/plan.md (re-Read it; the file was overwritten)
    Re-review ONLY the HIGH and MEDIUM findings you raised previously. Do not re-grade approved artifacts.
    Verdict format unchanged: APPROVE or CHANGES_REQUESTED with HIGH/MEDIUM/LOW findings."
})
```

After PLAN_APPROVED or PLAN_ESCALATED: shut down both challengers.

## Build Phase Dispatch

### Single Slice (subagent -- no team)

```
Agent({
  subagent_type: "frontend-engineer",
  isolation: "worktree",
  prompt: "Read ~/.claude/skills/build-implementation/SKILL.md and execute it fully.
    Read ~/.claude/agents/frontend-engineer.md for your role definition.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: Implement [feature], branch feature/X, base main.
    Acceptance criteria: [AC details]"
})
```

### Multi-Slice (team -- parallel engineers)

```
// Step 1: Create tasks
TaskCreate({ title: "Build: API endpoint for X", description: "ACs: ..." })
TaskCreate({ title: "Build: UI component for Y", description: "ACs: ..." })

// Step 2: Spawn teammates in single message, assign tasks
Agent({
  name: "backend-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "software-engineer",
  prompt: "Read ~/.claude/skills/build-implementation/SKILL.md and execute it fully.
    Read ~/.claude/agents/software-engineer.md for your role definition.
    Context: branch feature/X, base main.
    Your task: Build API endpoint for X. Check TaskList for details.
    Commit your work to a feature branch before completing."
})

Agent({
  name: "frontend-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "frontend-engineer",
  prompt: "Read ~/.claude/skills/build-implementation/SKILL.md and execute it fully.
    Read ~/.claude/agents/frontend-engineer.md for your role definition.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: branch feature/X, base main.
    Your task: Build UI component for Y. Check TaskList for details.
    Commit your work to a feature branch before completing."
})
```

After both complete: merge branches, shut down teammates.

### Planning Agent Dispatch (advisory, multi-slice Build only)

**Spawn condition**: `should_spawn_planning_agent(slice_count, dispatch_mode, phase)` returns True.
Evaluated at Build phase start, before build engineers are spawned.

**When spawned** (all must be true):
- `slice_count >= 2` (multi-slice Build)
- `dispatch_mode not in ("best-of-n", "pdr-rtv")` (planning-agent is incoherent in Best-of-N and PDR-RTV races — both are parallel candidate races with no shared evolving plan to refine)
- `phase != "fix"` (fix-engineer scope is narrower than the plan)

**Spawn** (simultaneously with build engineers in a single message):
```python
Agent({
  subagent_type: "planning-agent",
  team_name: "pipeline-{task-id}",
  name: "planning-agent",
  model: "sonnet",
  prompt: """
TaskId: {task-id}
PlanPath: pipeline-state/{task-id}/plan.md
ScratchpadDir: pipeline-state/{task-id}/scratchpad/
TeamRoster: {comma-separated names of build engineer teammates}
PollSeconds: 60

Read ~/.claude/skills/continuous-planning/SKILL.md and execute it fully.
Read ~/.claude/agents/planning-agent.md for your role definition and edit-scope guard.
"""
})
```

**Single-slice path is UNCHANGED.** When `slice_count < 2`, the planning-agent is not spawned and all existing single-slice Build dispatch logic is unmodified.

**Shutdown**: Send `SendMessage({type: "shutdown_request", name: "planning-agent"})` AFTER sending shutdown to build engineers (let plan have its final cycle).

**Verdict** (emitted by planning-agent before exit):
- `PLAN_REFINED` — at least one Plan Update was appended
- `PLAN_UNCHANGED` — no contradictions found

Both verdicts are acceptable. The orchestrator logs the verdict in pipeline state but does not gate Build completion on it. Planning is advisory.

**Cost**: ~$0.05/build typical (Sonnet 4.6, ~20 poll cycles × ~700 tokens). Worst-case $0.60 at 200-turn budget exhaustion (planning silently stops, Build continues).

### Best-of-N Build Team Dispatch (conditional — `bestofn:true` from intake)

When `/intake` has tagged the task `bestofn: true` (computed in Step 2d-bis as `critical OR user_override`, where `user_override` fires on the literal `[best-of-n]` token in the request text), the Build phase dispatches as a Team variant that runs the same slice across N candidate models in parallel and picks the best output. This is NOT a separate skill — it is a dispatch mode of the Build Team. The winner still faces the normal Review → Final Gate → Ship gates; scoring selects *which* candidate faces those gates, it does not substitute for them.

The previous threshold (`task_class=="feature" AND Budget>=5`) was tightened to criticality-only after baseline data showed the 2-3x spend was not justified for non-critical features. Users who still want Best-of-N on a non-critical task pass `[best-of-n]` in their request.

**Procedure:**

0. **Pre-flight resource check (Wave-2 B11.2)**: source `skills/best-of-n/lib/score.sh` and call `check_worktree_capacity` against the project repo. Default cap is **6 worktrees on workstations, 12 on CI** (`CI=true`); override via `CLAUDE_BESTOFN_MAX_WORKTREES`. If the cap is exceeded → log `fallback-to-single-engineer` to the pipeline state's `## Re-routes` section and dispatch the standard single-engineer Build instead. This protects against disk/inode pressure on hosts that already have parallel sessions or abandoned pipelines holding worktrees open. Falling back is silent — the pipeline never halts and never asks the user.
1. **Load roster** from `skills/best-of-n/config.json`. Default: Opus 4.7 + Sonnet 4.6 (always included) + an optional external-frontier slot (GPT-5.3-Codex / Gemini 3.1 Pro) gated behind `required_env`. Respect `max_candidates` as an upper bound.
2. **Validate candidates**: drop any whose `required_env` is unset and emit `[best-of-n] Skipping {slug}: {required_env} not set`. For external candidates, call `skills/best-of-n/external-runner.sh`; if it exits non-zero, drop the candidate. Must end with ≥ 2 candidates or the dispatch aborts with `BEST_OF_N_FAILED` and the pipeline falls back to the standard single-engineer Build dispatch.
3. **Spawn one engineer teammate per candidate** into the pipeline team in a single message:
   ```
   Agent({
     subagent_type: "software-engineer",    // or "frontend-engineer" for UI slices
     isolation: "worktree",
     model: "<agent_model_param>",          // "opus" / "sonnet" / "haiku"
     team_name: "pipeline-{task-id}",
     name: "boN-{slug}",
     mode: "bypassPermissions",
     prompt: "<slice spec + ACs>
              Read ~/.claude/skills/build-implementation/SKILL.md and execute fully.
              Commit to branch: build/{task-id}-boN-{slug}"
   })
   ```
   External candidates are dispatched via `skills/best-of-n/external-runner.sh` (honest stub today; returns non-zero until a provider is wired). **Do not fabricate results** for external runners that fail.
4. **Collect results** per candidate: branch, commit SHA, test exit code, shape violation count (run `hooks/code-shape-check.sh` across changed files on the branch), diff size (`git diff --stat main..<branch>`).
5. **Spawn ONE code-reviewer teammate for selection** with the rubric:
   - `test_pass`: 1 if all tests green else 0 (dominant — broken code cannot win)
   - `shape_compliance`: `max(0, 1 - violations/10)`
   - `subjective_quality`: reviewer's 1-5 score on clarity + correctness, with written justification
   - `diff_size`: tie-breaker term — captured per-candidate in Step 4 via `git diff --stat main..<branch>` (records both `changed_files` and `changed_lines`). Spec for tie-break ordering: `(changed_files, changed_lines)` ascending — fewer files first, fewer lines second. Today `score.sh::pick_winner` collapses this to a single `diff_size` value (the lines column) and `skills/best-of-n/config.json::tie_breaker_order` encodes only `["diff_size_asc", "cost_asc"]`; the file-count split (in both the script and the config array) is a follow-up code change, tracked separately and out of scope for this slice.
   - Composite: `test_pass*1000 + shape_compliance*100 + subjective_quality*20 - (diff_size/100)`
   - **Tie-breaker order** (fires when `subjective_quality` AND `shape_compliance` are equal across the test-passing candidates — among test-passers, the integer-stepped 20× subjective term dominates the composite, so equal subjective+shape is the principled "near-tie" boundary):
     1. Fewer changed files; then
     2. Fewer changed lines; then
     3. Cheaper executor tier (sonnet < opus < external-frontier, integer ranks 1/2/3).
   - **Divergence record (advisory, no gate, no new verdict)**: when the top two candidates clear the tie-breaker boundary above AND their changed-files sets have Jaccard < 0.5 (non-overlapping work on the same slice), append a `category: decision` finding to `pipeline-state/{task-id}/scratchpad/best-of-n-selection.md` with winner/runner-up SHAs, per-candidate diff-stat, and the verbatim `## Selection Rationale`. The dispatch never writes `category: anti-pattern` — recurring divergence is mined into anti-pattern instincts only by `/learn` Step 3d via the standard observations.jsonl path (see `skills/learn/SKILL.md` § 3d), gated on `recurrence>=3 AND phases.review.rounds>=2`. `category: decision` is in the scratchpad enum at `rules/_detail/autonomous-intelligence.md` § Pipeline Scratchpad and is forwarded to reviewers and Final Gate roles by the existing injection matrix.
   - Reviewer MUST write a `## Selection Rationale` section — copied verbatim to the scratchpad for future `/learn` runs. The diff-stat and the Jaccard value (when the divergence record fires) are quoted in the rationale.
6. **Merge & cleanup**:
   - `git merge --no-ff build/{task-id}-boN-{winner-slug}` into the pipeline's working branch
   - For every loser: `git worktree remove --force <path>` then `git branch -D build/{task-id}-boN-{slug}`
   - Write `pipeline-state/{task-id}/best-of-n.md` (frontmatter: task_id, phase=build, verdict=BEST_OF_N_COMPLETE, timestamp; sections: Candidates Run, Winner, Selection Rationale, Cost Estimate Per Candidate)
   - Append `category: decision` note to `pipeline-state/{task-id}/scratchpad/best-of-n-selection.md`
7. **Winner proceeds to standard Review** — Best-of-N does not skip review or any subsequent gate.

**Fallback**: on `BEST_OF_N_FAILED` (insufficient candidates or all candidates failed their own tests), fall back to the standard single-engineer Build dispatch. Log the fallback in pipeline state under `## Re-routes`. Never halts.

**Helpers** (orchestrator-side, not skills):
- `skills/best-of-n/config.json` — roster, selection weights, tie-breaker order
- `skills/best-of-n/lib/score.sh` — sourceable pure-bash `score_candidate`, `pick_winner`, `check_budget_gate`
- `skills/best-of-n/external-runner.sh` — extension point for non-Anthropic candidates (honest stub today)
- `skills/best-of-n/tests/test_best_of_n.sh` — deterministic test of scoring, cleanup, and budget gate

### PDR-RTV Build Team Dispatch (conditional — `pdr_rtv:true` from intake)

When `/intake` has tagged the task `pdr_rtv: true` (computed in Step 2d-bis as `budget >= ${CLAUDE_PDR_RTV_BUDGET_FLOOR:-9} OR critical == true`), the Build phase dispatches as a Team variant that scales test-time compute via T=2 iterations of N parallel rollouts, summary-based refinement, and pairwise tournament selection (arXiv:2604.16529). PDR-RTV is mutually exclusive with Best-of-N — when both flags fire, PDR-RTV wins as the strictly stronger variant (log re-route to pipeline state's `## Re-routes`). The winner still faces the normal Review → Final Gate → Ship gates; tournament selects *which* candidate faces those gates, it does not substitute for them.

The variant lives at `skills/pdr-rtv/` and reuses Best-of-N's helper infrastructure (`config.json` roster, `external-runner.sh`, `score.sh::check_worktree_capacity`).

**Procedure:**

0. **Pre-flight worktree-capacity check**: source `skills/best-of-n/lib/score.sh` and call `check_worktree_capacity` against the project repo. Default cap is 6 worktrees on workstations, 12 on CI; override via `CLAUDE_BESTOFN_MAX_WORKTREES`. Peak concurrent worktrees for PDR-RTV is N=4 (iter-0 worktrees are reaped before iter-1 spawns; see `skills/pdr-rtv/lib/dispatch.sh::reap_iteration_0_worktrees`). If the cap is exceeded → emit `PDR_NO_CONSENSUS` with `fallback_reason: "worktree-cap-exceeded"`, log the re-route to pipeline state's `## Re-routes`, and silently re-route to Best-of-N → standard. Never halts; never asks the user.

1. **Iteration 0 — fresh rollouts**: source `skills/pdr-rtv/lib/dispatch.sh` and call `dispatch_iteration 0`. The helper spawns N=4 parallel build engineers in a single message, each in its own worktree on branch `build/{task-id}-pdr-iter0-<slug>`. Each engineer's spawn prompt extends `software-engineer` with a `Self-Summarize` directive: at completion, write `pipeline-state/{task-id}/pdr-rtv/rollouts/<slug>/summary.md` with three required H2 sections (`## Hypotheses Tried`, `## Progress Made`, `## Failure Modes`) AND a `pipeline-state/{task-id}/pdr-rtv/rollouts/<slug>/meta` file with `sha:` and `diff_stat:` fields. Summaries persist OUTSIDE the worktree so iteration-0 worktrees can be reaped before iteration-1 spawns.

2. **Reap iteration 0**: call `reap_iteration_0_worktrees` AFTER all iter-0 summaries are persisted to `pipeline-state/`. The helper enumerates iter-0 worktree paths and runs `git worktree remove <path>` on each, releasing inodes/disk before iter-1 spawns. Peak concurrent worktrees stays at N=4 throughout.

   **Slug-validation contract (security, F2)**: before invoking `git worktree remove --force <path>` on any candidate, the orchestrator MUST verify the path appears in `git worktree list --porcelain` output for THIS repository. Slugs that do not resolve to a known worktree path are skipped with a forensic JSONL line at `metrics/{session}/pdr-rtv-events.jsonl` (`source: "reap-skipped-unknown-worktree"`). The lib-level `reap_iteration_0_worktrees` defends one layer up by skipping any directory entry whose slug fails `_pdr_validate_slug` (rejects `..`, leading `.`, slashes, and any non-`[a-zA-Z0-9_.-]` characters). The two-layer defense ensures a malicious or malformed slug cannot target unrelated worktrees outside the iter-0 set.

3. **Iteration 1 — refined rollouts**: call `dispatch_iteration 1`. The helper spawns N=4 parallel build engineers (branch `build/{task-id}-pdr-iter1-<slug>`), each receiving K=2 randomly-sampled iteration-0 summaries injected as a `## Refine From Prior Attempts` section in the spawn prompt. Sampling is deterministic given `CLAUDE_PDR_SEED` (default unset → fresh random). Iter-1 worktrees are reaped inside `dispatch_iteration` after each rollout's summary + meta is persisted.

4. **Tournament — pairwise summary comparison**: source `skills/pdr-rtv/lib/tournament.sh` and call `run_tournament` against the list of green-build slugs (across both iterations, expected 8 if all candidates succeeded). Tournament is single-elimination pairwise (G=2); bracket order is deterministic given seed. Each match invokes `_pdr_pick_winner`, which dispatches `patch-critic` in tournament mode:

   ```
   Agent({
     subagent_type: "patch-critic",
     model: "<advisor-paired sonnet+opus per agent frontmatter>",
     prompt: "<comparison instructions>
              Mode: tournament
              Candidates: <slug-A>,<slug-B>
              Read ~/.claude/agents/patch-critic.md and execute fully."
   })
   ```

   The orchestrator parses `WINNER: A|B` from the agent's stdout. Today the production picker `_pdr_pick_winner` returns a diff-stat heuristic placeholder when no test-seam override is set — this is the documented hand-off surface for the orchestrator-side `Agent` invocation. The diff-stat heuristic remains as a tie-breaker, NOT the primary verdict source. Tournament progresses log2(N×T) rounds (3 for default 8 candidates: 8→4→2→1).

5. **MODE_AMBIGUOUS surfacing (Path-B advisory today)**: when a tournament-mode spawn carries BOTH `Mode: tournament` AND `Persona: <name>` tokens (as a future multi-persona prompt-builder bug could inject), `hooks/pre-agent-advisor.sh` (PreToolUse) logs `source: "mode-ambiguous"` to `metrics/{session}/advisor-dispatch.jsonl` per `agents/patch-critic.md` § Tournament Mode AC8b. The orchestrator MUST parse this forensic line at tournament conclusion and surface the offending match as `PATCH_REJECTED` (per AC8b verbatim) — propagate as `PDR_NO_CONSENSUS` with `fallback_reason: "all-finalists-rejected"` if the rejection eliminates the final pair. The hook is currently log-only because the Agent input schema does not yet expose the relevant fields; promotion to enforcement is a single-line flip in `hooks/pre-agent-advisor.sh` when the schema lands. The orchestrator-side `MODE_AMBIGUOUS → PATCH_REJECTED` surfacing is decoupled from the hook's promotion timeline.

6. **Verdict & merge**: `run_tournament` writes `pipeline-state/{task-id}/pdr-rtv/tournament.md` with the full bracket (N-1 round entries), the `## Winner` section (slug + SHA + verbatim selection rationale), and the cost estimate. The orchestrator merges the winner branch into the pipeline working branch (`git -C "$WORKTREE" merge --no-ff build/{task-id}-pdr-iter<N>-<winner-slug>`) and removes loser worktrees + branches. Emits:
   - `PDR_WINNER_SELECTED` (success): winner proceeds to standard Review (`/code-review` + `/security-review` per `rules/_detail/pipeline-protocol.md`).
   - `PDR_NO_CONSENSUS` (failure): silent re-route to Best-of-N → standard. Log to pipeline state's `## Re-routes` with one of three `fallback_reason` enum values:
     - `worktree-cap-exceeded` (Step 0 above)
     - `insufficient-green-builds` (<4 candidates produced green builds across both iterations)
     - `all-finalists-rejected` (tournament verifier rejected every finalist via `PATCH_REJECTED` propagation)

**Pipeline state** (`pipeline-state/{task-id}/pdr-rtv.md`):

```yaml
---
task_id: {task-id}
phase: build
verdict: PDR_WINNER_SELECTED | PDR_NO_CONSENSUS
fallback_reason: null | worktree-cap-exceeded | insufficient-green-builds | all-finalists-rejected
timestamp: {ISO 8601}
---

## Iterations
- iter0: {green count}/{N} green builds, {failed count} failures
- iter1: {green count}/{N} green builds, {failed count} failures

## Tournament Bracket
{See pipeline-state/{task-id}/pdr-rtv/tournament.md for full match log}

## Winner
- slug: {winner-slug}
- sha: {commit SHA}
- branch: build/{task-id}-pdr-iter1-{winner-slug}

## Total Cost USD
{cost_estimate_usd from observation}

## Re-routes
{empty on PDR_WINNER_SELECTED; populated on PDR_NO_CONSENSUS with fallback_reason}
```

**Cost envelope** at default settings (N=4, T=2): 8 sequential rollouts + 7 tournament comparisons ≈ 4-5× standard Build cost. Justifies the `budget >= 9` trigger floor pending empirical baseline.

**Helpers** (orchestrator-side, not skills):
- `skills/pdr-rtv/config.json` — N, T, K, max_runtime, seed
- `skills/pdr-rtv/lib/distill.sh` — sourceable `distill_rollout` (writes summary.md outside the worktree)
- `skills/pdr-rtv/lib/dispatch.sh` — sourceable `dispatch_iteration`, `reap_iteration_0_worktrees`
- `skills/pdr-rtv/lib/tournament.sh` — sourceable `run_tournament`, `_pdr_pick_winner` (diff-stat tie-breaker)
- `skills/best-of-n/lib/score.sh` — reused `check_worktree_capacity` for pre-flight (B11.2 helper)

**Observation schema**: see `rules/_detail/autonomous-intelligence.md` § Observation Capture / `phases.pdr_rtv` for the full field reference (verdict, n_candidates_iter0, n_candidates_iter1, tournament_rounds, winner_slug, cost_estimate_usd, optional fallback_reason).

## Review Phase Dispatch

Always uses the team. Spawn both reviewers in a single message:

```
// Step 1: Get the diff (orchestrator does this once)
git diff main...HEAD

// Step 2: Create tasks
TaskCreate({ title: "Code review: feature X", description: "Diff attached..." })
TaskCreate({ title: "Security review: feature X", description: "Diff attached..." })

// Step 3: Spawn reviewers
Agent({
  name: "code-reviewer",
  team_name: "pipeline-{task-id}",
  subagent_type: "code-reviewer",
  prompt: "Read ~/.claude/skills/code-review/SKILL.md and execute it fully.
    Read ~/.claude/agents/code-reviewer.md for your role definition.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: branch feature/X, base main.
    Changed files: [list]
    Full diff:
    [git diff output]
    Prior verdict: BUILD_COMPLETE

    Build agent decision record:
    [Decision Record from build state file — why choices were made]

    Build agent context for review:
    [Context for Review from build state file — uncertainty flags, areas needing focus]

    Agent memory (if exists):
    [Contents of agent-memory/code-reviewer/{project-hash}/memory.md]

    Learned patterns for this project (if any):
    [Top 5 instincts from learning/instincts/ filtered to role: code-reviewer]"
})

Agent({
  name: "security-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "security-engineer",
  prompt: "Read ~/.claude/skills/security-review/SKILL.md and execute it fully.
    Read ~/.claude/agents/security-engineer.md for your role definition.
    Also read ~/.claude/skills/react-native-patterns/SKILL.md for tech-specific guidance.
    Context: branch feature/X, base main.
    Changed files: [list]
    Full diff:
    [git diff output]
    Prior verdict: BUILD_COMPLETE

    Build agent decision record:
    [Decision Record from build state file — why choices were made]

    Agent memory (if exists):
    [Contents of agent-memory/security-engineer/{project-hash}/memory.md]

    Learned patterns for this project (if any):
    [Top 5 instincts from learning/instincts/ filtered to role: security-engineer]"
})
```

### Adversarial Review (Budget >= 10 OR Sensitive Code)

When the pipeline triggers adversarial review, spawn two code-reviewers with different focus prompts:

```
Agent({
  name: "reviewer-design",
  team_name: "pipeline-{task-id}",
  subagent_type: "code-reviewer",
  prompt: "Read ~/.claude/skills/code-review/SKILL.md and execute it fully.
    Read ~/.claude/agents/code-reviewer.md for your role definition.
    FOCUS: abstractions, naming clarity, DRY/SOLID, design quality, pattern appropriateness.
    DO NOT focus on edge cases or error paths (another reviewer handles that).
    Context: branch feature/X, base main.
    Changed files: [list]
    Full diff: [git diff output]"
})

Agent({
  name: "reviewer-edges",
  team_name: "pipeline-{task-id}",
  subagent_type: "code-reviewer",
  prompt: "Read ~/.claude/skills/code-review/SKILL.md and execute it fully.
    Read ~/.claude/agents/code-reviewer.md for your role definition.
    FOCUS: edge cases, error paths, integration concerns, race conditions, concurrency issues.
    DO NOT focus on naming or design patterns (another reviewer handles that).
    Context: branch feature/X, base main.
    Changed files: [list]
    Full diff: [git diff output]"
})
```

After both return:
- Findings flagged by both → HIGH confidence
- Findings flagged by only one → MEDIUM confidence (include both perspectives)
- Both APPROVE → advance. Either CHANGES_REQUESTED → normal review loop with the raising reviewer.

### Review Loop with Teams

On CHANGES_REQUESTED:

```
// 1. Spawn fix-engineer into the same team
//    NOTE: fix-engineer is its own agent (agents/fix-engineer.md) — it
//    operates on the prior build's worktree (NOT a fresh worktree) and
//    has fix-cycle-specific guidance (verify finding validity first,
//    no scope creep, no compliance commit messages, no source-code
//    apology comments).
Agent({
  name: "fix-engineer",
  team_name: "pipeline-{task-id}",
  subagent_type: "fix-engineer",
  // Pass the prior build's worktree path so the fix targets the same
  // branch the build engineer produced. The path comes in via the
  // prompt's `Working directory:` line (see agents/fix-engineer.md
  // § Where You Run). Do NOT pass `isolation: "worktree"` here — that
  // creates a fresh worktree off main without the build's commits, so
  // the fix lands on the wrong tree and `git diff main...HEAD` shows
  // nothing for the fix-engineer to address. This is a known pitfall
  // — reproduced in the wave5-hygiene rev1 fix cycle (May 2026).
  prompt: "Read ~/.claude/agents/fix-engineer.md for your role definition.
    Working directory: <prior-build-worktree-path>
    Branch: <feature-branch-the-build-was-on>
    Round: 1 (or 2 on re-review)
    Findings to address: [verbatim reviewer text + cited file:line]
    Build diff: [git diff main...HEAD]
    Verify each finding is valid before implementing.
    If a suggestion would make code worse, return verdict
    FIX_REJECTED_TECHNICAL with justification.
    Commit with descriptive message (not 'fixed per review feedback')."
})

// 2. After fix-engineer completes, shut it down
SendMessage({ to: "fix-engineer", message: { type: "shutdown_request" } })

// 3. Merge fix branch, then re-assign to raising reviewer (STILL ALIVE)
SendMessage({
  to: "code-reviewer",
  message: "Re-review: Finding F1 (method body > 8 lines) was addressed.
    Fix diff: [diff]. Check the fix addresses the finding.
    Re-review ONLY the addressed findings, not the full codebase."
})
```

The reviewer **already has context** from the first review. No prompt reconstruction needed.

**Fix agent review-receiving rules** (include in fix agent prompt):
- Verify the reviewer's finding before implementing -- read the cited code, confirm the concern applies
- If the suggestion would make code worse, report back with technical justification instead of blindly complying
- Commit messages describe WHAT changed and WHY -- never "fixed per review feedback"

Maximum 2 total rounds (initial + 1 re-review). If not resolved, escalate to user.

After both APPROVE: shut down both reviewers.

## Final Gate Phase Dispatch

Three phases that currently run sequentially now run in parallel:

```
// Step 1: Create tasks
TaskCreate({ title: "Verify: contract + smoke + mutation", description: "..." })
TaskCreate({ title: "Test: coverage analysis + gap filling", description: "..." })
TaskCreate({ title: "Accept: AC validation + UX review", description: "..." })

// Step 2: Spawn all three in single message
Agent({
  name: "verifier",
  team_name: "pipeline-{task-id}",
  subagent_type: "qa-engineer",
  prompt: "Read ~/.claude/skills/verify/SKILL.md and execute it fully.
    Read ~/.claude/agents/qa-engineer.md for your role definition.
    Context: branch feature/X, all tests passing, review APPROVED.
    Run contract tests, smoke tests, and mutation testing on changed files."
})

Agent({
  name: "test-analyst",
  team_name: "pipeline-{task-id}",
  subagent_type: "qa-engineer",
  prompt: "Read ~/.claude/skills/qa-test-strategy/SKILL.md and execute it fully.
    Read ~/.claude/agents/qa-engineer.md for your role definition.
    Context: branch feature/X, ACs: [list].
    Map ACs to tests, identify coverage gaps, write missing tests."
})

Agent({
  name: "product-reviewer",
  team_name: "pipeline-{task-id}",
  subagent_type: "product-reviewer",
  prompt: "Read ~/.claude/skills/product-acceptance/SKILL.md and execute it fully.
    Read ~/.claude/agents/product-reviewer.md for your role definition.
    Context: branch feature/X, ACs: [list].
    Validate all ACs are met, assess UX quality, verify business value."
})
```

After all three return verdicts: shut down teammates.

## Multi-Persona Patch Critic Dispatch (critical OR Budget >= 7)

The patch-critic role in the Final Gate Team has two dispatch modes selected by criticality + budget. The other three Final Gate roles (verify + test + accept) are unchanged.

| Mode | Gate condition | Spawn shape |
|---|---|---|
| single-critic (default) | `!critical AND Budget < 7` | one `patch-critic` Agent call alongside verifier/test-analyst/product-reviewer |
| multi-persona variant | `critical == true OR Budget >= 7` | three parallel `patch-critic` Agent calls, one per persona, alongside verifier/test-analyst/product-reviewer |

Background: inspired by Multi-Agent Reflexion (Yu et al., arXiv 2512.20845) where multiple persona-critics escape single-agent confirmation bias. Cost is ~3x patch-critic spend; the gate already runs in parallel with verify+test+accept and is a rounding error vs build/review spend on critical work.

**Composition with C8 anti-pattern mining (#80)**: complementary, not redundant. Multi-persona catches in-cycle (during this gate); C8 mines cross-pipeline patterns from observation rounds-counts after pipelines close. The schema extension in `rules/_detail/autonomous-intelligence.md` § Observation Capture (`phases.patch_critic.rounds`) wires the variant's rejections into C8's mining gate so consistently-caught-but-not-by-code-review patterns become anti-pattern instincts over time. They cover different time horizons.

**Procedure (variant mode):**

1. **Gate check**: read pipeline state. If `critical != true AND Budget < 7`, dispatch single-critic and skip the rest of this procedure.

2. **Spawn three personas in a single message** (parallel — no persona sees another persona's output):

   ```
   Agent({
     name: "patch-critic-correctness",
     team_name: "pipeline-{task-id}",
     subagent_type: "patch-critic",
     prompt: "Read ~/.claude/agents/patch-critic.md for your role definition.

       Persona: correctness
       Weight § 1 (Tests cover the change) and § 5 (Accessibility) heaviest.
       Search emphasis: 'Did the diff actually solve the spec? Are tests load-bearing
       for the behavior change?'

       You score every rubric dimension regardless of specialty. You do NOT see the
       other personas' outputs. Independent context is the design.

       Context: branch feature/X, base main.
       Candidate diff: [git diff main...HEAD]
       Test output: [most recent fresh test-suite run]
       Intake spec: [task description]
       A11y index (if present): pipeline-state/{task-id}/design-qc/index.json
       ## Execution Evidence  # ← optional block — conditionally injected only when CLAUDE_PATCH_CRITIC_EXEC_LAYER=1 AND Steps 1-3 all succeed; absent by default"
   })

   Agent({
     name: "patch-critic-regression-risk",
     team_name: "pipeline-{task-id}",
     subagent_type: "patch-critic",
     prompt: "Read ~/.claude/agents/patch-critic.md for your role definition.

       Persona: regression-risk
       Weight § 3 (No obvious regressions visible from diff) heaviest.
       Search emphasis: 'What worked before this diff that could break now?
       Removed null guards, weakened validation, broadened catches that swallow
       errors, lost edge-case branches, removed tests, changed defaults that
       callers rely on.'

       You score every rubric dimension regardless of specialty. You do NOT see the
       other personas' outputs. Independent context is the design.

       Context: branch feature/X, base main.
       Candidate diff: [git diff main...HEAD]
       Test output: [most recent fresh test-suite run]
       Intake spec: [task description]
       ## Execution Evidence  # ← optional block — conditionally injected only when CLAUDE_PATCH_CRITIC_EXEC_LAYER=1 AND Steps 1-3 all succeed; absent by default"
   })

   Agent({
     name: "patch-critic-scope-creep",
     team_name: "pipeline-{task-id}",
     subagent_type: "patch-critic",
     prompt: "Read ~/.claude/agents/patch-critic.md for your role definition.

       Persona: scope-creep
       Weight § 2 (Diff minimal vs spec) and § 4 (No incidental refactor) heaviest.
       Search emphasis: 'What is in this diff that the spec did NOT ask for?
       Renames, moves, reorgs, drive-by cleanups, opportunistic typing tweaks.'

       You score every rubric dimension regardless of specialty. You do NOT see the
       other personas' outputs. Independent context is the design.

       Context: branch feature/X, base main.
       Candidate diff: [git diff main...HEAD]
       Test output: [most recent fresh test-suite run]
       Intake spec: [task description]
       ## Execution Evidence  # ← optional block — conditionally injected only when CLAUDE_PATCH_CRITIC_EXEC_LAYER=1 AND Steps 1-3 all succeed; absent by default"
   })
   ```

3. **Aggregation rule (OR)**:
   - All three personas return `PATCH_APPROVED` → gate verdict `PATCH_APPROVED`.
   - Any persona returns `PATCH_REJECTED` (any MEDIUM+ severity finding on any dimension) → gate verdict `PATCH_REJECTED`. Forward findings from ALL rejecting personas to fix-engineer.
   - The orchestrator MUST NOT silently override a single-persona MEDIUM+ rejection because the other two passed. OR-aggregation is the design, not a soft hint.

4. **Audit artifact**: write `pipeline-state/{task-id}/patch-critic.md` with frontmatter (`task_id, phase=final-gate, verdict, timestamp, mode=multi-persona`) and three sections (one per persona). Include each persona's full Rubric table + Findings list verbatim. The orchestrator-aggregated verdict appears in frontmatter and at the top of the file.

5. **Divergence record on split votes** (one persona REJECTs, others PASS — i.e., not unanimous): append a `category: decision` finding to `pipeline-state/{task-id}/scratchpad/patch-critic-divergence.md`. Pattern matches Best-of-N's divergence record. Body includes: rejecting persona, dimension, severity, finding text, file:line. `/learn` mines split-vote dimensions over time; consistently-split dimensions are calibration targets (rubric clarity issue, not a persona problem).

6. **PATCH_REJECTED → fix → re-critique ALL personas** (NOT just the rejecting persona). Differs from existing Review pattern (re-dispatch only the rejecting reviewer). The fix may have introduced a new issue in another persona's territory. Cost is acceptable on critical/Budget>=7 work. Maximum 2 total rounds (initial + 1 re-critique), matching the existing Review cap. After 2 rounds with persistent rejection → escalate to user. Should be rare under the In-Cycle Fix Rule.

7. **Partial completion contract**: if a persona fails to return within timeout (`CLAUDE_SUBAGENT_MAX_RUNTIME`, default 1800s), treat as `PATCH_REJECTED` with reason `persona-timeout`. Re-dispatch only the missing persona (1 retry). After 2 timeouts on the same persona → escalate per retry-twice-then-escalate. Do NOT silently skip a timed-out persona — a missing verdict is not an approval.

8. **Observation capture** (Reflect step): record per-persona verdicts and rejecting findings in `phases.patch_critic` per `rules/_detail/autonomous-intelligence.md` § Observation Capture. The `rounds` count and `persona_rejections` array feed C8 anti-pattern mining on subsequent pipelines.

**Why no debate round (vs the paper)**: patch-critique is closed-form (fixed rubric, fixed dimensions, binary-per-finding-after-severity). The paper's debate coordinator targets open-ended reflexion (HotPotQA answers, HumanEval code generation). Three independent strict scorers + OR-aggregation captures the "different priors → different blind spots" lift without the 2x debate-round overhead.

### Execution Evidence (optional, default off)

OPTIONAL enrichment that prepends a short `## Execution Evidence` block to every persona spawn prompt before dispatch. Inspired by Agentic Verifier (arXiv 2602.04254), where giving the verifier execution traces of the candidate against discriminative inputs catches a class of regression that diff-only review misses. The path is purely additive — when the flag is unset OR any of three downstream steps silently skip, the dispatch falls through to the existing #93 procedure exactly (`1. Gate check` → `2. Spawn three personas` → `3. Aggregation rule (OR)` → … unchanged).

**Step 0 — Env-var probe**:

- Read `CLAUDE_PATCH_CRITIC_EXEC_LAYER` from the orchestrator-side env. Defaults unset / off. Only the literal value `1` enables the path; any other value (including empty, `0`, `true`, `yes`) coerces to off — the same conservative pattern used by other harness opt-in flags.
- When unset / off → SKIP the entire sub-section. Dispatch personas exactly as #93 specifies (Step 1 onward in this section). This is the default and the path THIS pipeline's own Final Gate runs against; the env var is operator-set, never harness-set (enforced as a committed invariant by the AC3.7 grep guard shipping in Slice 3).

**Step 1 — Generate discriminative test inputs**: ONCE per slice, the orchestrator issues ONE Claude call asking for 2–3 discriminative inputs that "would behave differently before vs after this candidate diff". The call shape mirrors Tier 3.5's cost-guardrail clause from `skills/verify/SKILL.md` § 4.25 verbatim — ONE call, NO retry, max 3 inputs per response (any extras are truncated to 3 by the orchestrator before splicing).

- **JSON schema (response shape — three required fields per input)**:
  ```
  {
    description:          string,
    input:                string|object,
    expected_distinction: string
  }
  ```
  - `description`: a one-line plain-English summary of the input's intent (string).
  - `input`: the actual input value passed to the candidate at run time. May be a `string` (e.g. a CLI argument, stdin payload) or an `object` (e.g. a structured request body).
  - `expected_distinction`: a one-line description of how the candidate's behavior is expected to differ between the pre-patch and post-patch revisions on this input (string). The generator's hypothesis about WHY the input is discriminative — used by personas as additional reasoning context, not as a pass/fail oracle.

- **Output sanitization (LLM output is untrusted, even from an internal call — prompt-injection embedded in the diff or downstream-fetched files can propagate through)**:
  - Per-field byte cap: each input's `description`, `input` (when serialized), and `expected_distinction` MUST NOT exceed 2KB (2048 bytes). Fields exceeding the cap → silent skip (treat the entire generator response as a failure).
  - Control-character strip: ASCII control characters below `0x20` (except newline `0x0A` and tab `0x09`) MUST NOT appear in any field. Any control-char detection → silent skip.
  - Total response cap: the entire JSON response payload MUST NOT exceed 8KB (8192 bytes). Oversized payloads → silent skip (never spliced into persona prompts).

- **Failure modes (each triggers a silent skip → fall through to diff-only dispatch, the same path as Step 0's flag-off fallback)**:
  - Call timeout — the LLM call exceeds the orchestrator-side timeout budget.
  - Parse failure — the response is malformed JSON or fails schema validation.
  - Zero non-equivalent inputs — the generator returns no inputs that distinguish pre- vs post-patch behavior.
  - Output over cap — any per-field byte cap or the total response cap is exceeded (sanitization failure).
  - Control-char strip — any field contains ASCII control characters below `0x20` (except newline / tab).

  Any one of the above → silent skip → fall through to diff-only dispatch (same fallback as Step 0's flag-off path; personas never observe the difference). No retry, no error log surfaced to the operator beyond the standard `phases.patch_critic.evidence_mode = "diff-only"` forensic record.

**Step 2 — Run candidate against discriminative inputs**: ONCE per slice, after the validated generator response from Step 1, the orchestrator applies the candidate diff in an ephemeral sandbox, executes the patched code against each input, captures the output, and reverts before the next input. The loop mirrors Tier 3.5's apply-test-revert pattern in `skills/verify/SKILL.md` § 4.25 verbatim; the verbiage is reused so a single canonical pattern source covers both verify-time mutation testing and patch-critic execution evidence.

- **Apply-test-revert loop (per discriminative input)**:
  1. Snapshot the worktree state — either via `git stash` push OR by checking out the candidate diff in a fresh scratch worktree under the harness sandbox root. NEVER apply the diff in-place to the active worktree.
  2. Apply the candidate diff to the snapshot.
  3. Execute the patched code against the input — the inferred entry point receives the input value (CLI argv for `string` inputs, JSON-decoded stdin for `object` inputs).
  4. Capture stdout, stderr, exit code, and elapsed-ms wall-clock.
  5. Revert: pop the stash OR delete the scratch worktree. The orchestrator MUST verify the revert succeeded (worktree is clean, HEAD matches pre-loop SHA) before applying the next input — a partial revert leaks state into the next run.

- **Sandbox isolation requirements (HARD — `chdir` alone is NOT sufficient)**: the run executes in an ephemeral worktree or container, never against the active worktree or REPO_ROOT. Required properties:
  - **Network egress denied** — no outbound network access from the sandbox (e.g. firewall rule, container network=none, PF block).
  - **Filesystem write confined to a scratch dir** — writes outside the sandbox tempdir / scratch-worktree fail at the OS level.
  - **CPU / memory caps** — `ulimit` or container limits prevent runaway resource consumption from a malicious or buggy candidate.
  - **No inheritance of harness env** — `ANTHROPIC_API_KEY`, git credentials, `GITHUB_PERSONAL_ACCESS_TOKEN`, and any harness-specific env var (including `CLAUDE_*` variables) MUST be unset in the sandbox env. The candidate cannot exfiltrate secrets it never sees.
  - **JSON-only deserialization at the boundary** — for `object` inputs, the test runner deserializes via JSON only; YAML, pickle, and arbitrary-code deserializers are rejected at the boundary (matching the Slice 2 generator schema's `string|object` typing).

- **Per-input timeout**: 30s per input is the orchestrator-side documented default (no new env var). The value mirrors Tier 3.5's per-mutant timeout convention in `skills/verify/SKILL.md` § 4.25 — the canonical timeout lives in Tier 3.5; this section quotes that value as a default and points back. If the candidate timing requirement diverges, change Tier 3.5's documented value first; do NOT introduce a parallel knob here.

- **Defense-in-depth caps at the execution-input boundary**: the Slice 2 caps (2KB per-field, 8KB total) are RE-VALIDATED here when serializing each input for argv / stdin to the candidate. If a generator-validated input exceeds the caps when serialized for execution, fail-closed → silent skip → diff-only fallback. Defense in depth — if Slice 2 sanitization is ever weakened or bypassed, the execution layer's own caps catch the over-cap input before it reaches a subprocess argv.

- **Run-failure modes (each rolls up under the existing "Run / execution failure" skip point — NOT a new top-level skip point)**:
  - **Sandbox unavailable** — the harness sandbox root cannot be created, the container runtime is missing, or the scratch-worktree allocation fails.
  - **No inferable entry point** — the orchestrator cannot identify a runnable surface for the candidate diff (no main module, no exported function, no CLI entry).
  - **All inputs time out** — every discriminative input from Step 1 hits the per-input 30s timeout; no input produces a usable result.

  Any one of the above → silent skip → fall through to diff-only dispatch (same fallback as Step 0's flag-off path AND Step 1's generator-failure path; personas never observe the difference). No retry, no error log surfaced beyond `phases.patch_critic.evidence_mode = "diff-only"`. The run-failure modes are ADDITIVE to Step 1's generator-failure modes, NOT replacements — both rolls up live in the single "Three silent skip points" enumeration below.

**Step 3 — Format and append evidence**: ONCE per slice, after Step 2 produces a list of `(input, run-result)` pairs, the orchestrator formats them into a single `## Execution Evidence` markdown block and APPENDS the SAME block VERBATIM to each of the three persona spawn prompts before the personas are spawned. The block is identical across all three personas — once-per-slice contract, no per-persona variation.

- **Block format (5 fields per discriminative input)**:
  1. `description` — the generator's one-line plain-English summary of the input's intent (verbatim from Step 1's validated response).
  2. `input` — the actual input value passed to the candidate (verbatim from Step 1; serialized as JSON when an `object`, quoted when a `string`).
  3. `run output (stdout / stderr)` — the captured output from Step 2, fence-wrapped (see sanitization below) so it cannot close the evidence block early.
  4. `exit code` — the candidate process's integer exit status from Step 2.
  5. `elapsed-ms` — wall-clock duration of the run from Step 2, in milliseconds.

- **Output sanitization at the execution-output boundary (defense-in-depth — REUSES Slice 2 caps verbatim)**:
  - **Per-field byte cap**: `stdout`, `stderr`, and the exit-code marker are each independently capped at 2KB (2048 bytes); content exceeding the cap is truncated with a trailing `... [truncated]` marker.
  - **Total spliced-block cap**: the full `## Execution Evidence` block MUST NOT exceed 8KB (8192 bytes) when assembled; oversized blocks → silent skip → diff-only fallback (treat as a Step 2 run failure, not a separate skip class).
  - **ANSI escape-sequence strip**: ASCII control sequences matching `\x1b[...m` (CSI / SGR) are stripped from `stdout` and `stderr` before splicing — terminal-injection vector closed at the boundary.
  - **Markdown fence escape**: literal backtick fences (` ``` `) and `## ` line-start markdown headers in `stdout` / `stderr` are escaped or fence-wrapped (e.g. `<execution-stdout>...</execution-stdout>`-style XML-like wrapper) so candidate output cannot close the evidence block early and inject persona-prompt material. Output that escapes the evidence block reaches persona reasoning context — same severity as a generator-side prompt-injection vector (Slice 2).

- **Block layout (identical across personas — once-per-slice)**: the markdown form below is what the orchestrator splices into each persona's spawn prompt. Personas treat the block as additional reasoning context for the existing rubric dimensions (rubric UNCHANGED — see `agents/patch-critic.md`).

  ```markdown
  ## Execution Evidence

  Generator + sandboxed run results — once-per-slice, identical across personas.

  ### Input 1
  - description: <generator description>
  - input: <input value>
  - exit code: <int>
  - elapsed-ms: <int>
  - run output:
  <execution-stdout>
  <captured stdout — sanitized, ANSI-stripped, fence-escaped, truncated to 2KB>
  </execution-stdout>
  <execution-stderr>
  <captured stderr — same sanitization>
  </execution-stderr>

  ### Input 2
  ...
  ```

**Once-per-slice contract**: when the flag is on AND the path proceeds, the orchestrator generates discriminative test inputs ONCE per slice, runs them ONCE, formats the result into a single `## Execution Evidence` block, and APPENDS the SAME block VERBATIM to each of the three persona spawn prompts. Evidence is shared across personas because (a) inputs are derived from the diff and the diff is identical across personas, so per-persona inputs would be identical too, and (b) persona differentiation already lives in the existing search-emphasis prompts (rubric-dimension weighting), not in raw evidence. The once-per-slice scope is both 3x cheaper and signal-equivalent — per-persona generation would produce identical inputs (the diff is identical), wasting the spend.

**Three silent skip points** — any one collapses to identical diff-only dispatch (no error surfaced, no log noise, persona spawns unchanged):

1. Flag off (Step 0 above) — env var unset or any value other than `1`.
2. Generator failure — the discriminative-test-input LLM call times out, returns malformed JSON, or returns zero non-equivalent inputs (Slice 2).
3. Run / execution failure — sandbox unavailable, no inferable entry point, or all inputs time out during the apply-test-revert loop (Slice 3).

Each skip point falls through to the existing dispatch exactly as #93 specifies; the personas never observe the difference, the rubric is unchanged, the verdict semantics are unchanged.

**Re-critique semantics**: when patch-critic returns `PATCH_REJECTED` and fix-engineer produces an updated diff, the orchestrator regenerates the execution-evidence block from scratch on each re-dispatch — the diff has changed, so the discriminative inputs and run output may differ. There is NO caching across rounds; per-dispatch regeneration is the contract.

**Forensic record**: the observation-schema `phases.patch_critic.evidence_mode` field (see `rules/_detail/autonomous-intelligence.md` § Field reference) records `"diff-only"` when any skip point fires (or when the flag is unset) and `"diff+execution"` only when all three steps complete successfully. Readers MUST tolerate absence of the field as a legacy / pre-exec-layer record.

Slices 2 and 3 land Steps 1-3 (input generation, sandboxed run, prompt-append point). This sub-section established Step 0 (the gate) and the silent-fallback semantics in Slice 1; subsequent slices extended the sub-section without altering the gate or the fallback contract.

**Hedges (PROVISIONAL until baseline run)**:

- Variant gated on `critical OR Budget >= 7`. Single-critic remains the default for routine work — DO NOT enable for `!critical AND Budget < 7`.
- OR-aggregation is intentionally conservative (biased toward false positives). Fix-engineer absorbs the rework cost; a missed regression at Final Gate costs more than an extra fix-engineer round.
- Disagreement rate is the kill-switch metric. If `/forensics` reports < 5% persona disagreement over a 30-pipeline window, drop back to single critic — the variant is no longer earning its 3x spend. If disagreement is > 30%, the personas are catching distinct things — variant justified. The 5–30% band is the working range.
- Empirical baseline is REQUIRED before promoting from PROVISIONAL. Baseline establishes false-positive rate vs single-critic on the harness regression suite (`/internal-eval`). The paper's HumanEval lift (76% → 82% Pass@1) does NOT directly translate to patch-critique acceptance/rejection — different domain, different decision shape.

## Teammate Shutdown

After each team phase completes:

```
SendMessage({ to: "teammate-name", message: { type: "shutdown_request" } })
```

After pipeline completes, clean up:
- Shut down any remaining teammates
- Team files at `~/.claude/teams/pipeline-{task-id}/` are auto-cleaned
- Task list at `~/.claude/tasks/pipeline-{task-id}/` is auto-cleaned

## Inter-Agent Communication (hcom)

When hcom is installed and hooks are registered:

### File Collision Detection
During multi-slice Build with parallel worktrees, hcom watches for file edits across agents. If two agents modify the same file within 30 seconds, hcom emits a collision warning via stderr. This prevents merge conflicts from being discovered at merge time — catching them while agents are still working.

### Direct Messaging During Team Phases
Teammates can message each other via hcom without routing through the orchestrator:
- Useful for: reviewer asking build-engineer a question, engineer notifying reviewer of a fix
- Messages arrive mid-turn or wake idle agents

### Activation
hcom hooks should only be active during team phases (check `CLAUDE_PIPELINE_TASK_ID` is set). Disable for solo subagent phases to avoid noise. The hcom hooks are gated by the presence of the pipeline task ID env var.

### Transcript Sharing
hcom enables transcript sharing for context handoffs — e.g., the architect's design reasoning is available to the software-engineer without the orchestrator reconstructing it in a prompt.

## Waiting for Checkpoints

Use `scripts/await-pattern.sh` instead of sleep-poll loops when waiting for a background process or teammate to reach a known-ready state.

**Usage:**

```bash
# Start background process, redirect stdout to a log file
nohup some-command >"$log" 2>&1 &
BG_PID=$!

# Block until checkpoint marker appears or timeout fires
scripts/await-pattern.sh "$log" '\[CHECKPOINT\] tests-green' 600 50000
case $? in
  0)   echo "Checkpoint reached" ;;
  124) echo "Timed out after 600s"; kill "$BG_PID" ;;
  1)   echo "Error (bad args, missing log, or max_lines exceeded)" ;;
esac
```

**Exit codes:** 0=matched, 124=timeout (matches GNU `timeout` convention), 1=bad-args/missing-file/max_lines-exceeded

**Logging:** every call appends one JSONL record to `metrics/${CLAUDE_SESSION_ID}/await-events.jsonl` with `record_type: await_match | await_timeout`.

**Checkpoint vocabulary:** See `rules/_detail/parallel-dispatch-protocol.md § Checkpoint Vocabulary` for standard marker strings.

### Deprecation: Sleep-Poll Loops

Sleep-poll loops are deprecated in orchestrator code:

```bash
# DEPRECATED — do not write new code like this
while ! grep -q '\[CHECKPOINT\] tests-green' "$log"; do
  sleep 2
done
```

Problems with sleep-poll: wastes CPU on idle wakeups, racy against line-buffered output, no structured audit trail, no timeout enforcement, no max_lines protection.

Use `await-pattern.sh` instead.

## Audit Trail

For each team phase, the orchestrator records:

```
[Build] TEAM PHASE -- 2 engineers spawned (backend-engineer, frontend-engineer)
[Build] COMPLETE -- both tasks done, branches merged
[Review] TEAM PHASE -- code-reviewer + security-engineer spawned
[Review] VERDICTS -- code-reviewer: APPROVE, security-engineer: CHANGES_REQUESTED (1 HIGH)
[Review] FIX -- fix-engineer spawned, fixing: [finding]. Shut down after fix.
[Review] RE-REVIEW -- re-assigned to security-engineer (context preserved)
[Review] VERDICT -- security-engineer: APPROVE
[Review] COMPLETE -- both APPROVE, reviewers shut down
[Final Gate] TEAM PHASE -- verifier + test-analyst + product-reviewer spawned
[Final Gate] VERDICTS -- VERIFIED + COVERED + APPROVED
[Final Gate] COMPLETE -- all shut down
```

## Batch Execution (Pre-Planned Work)

When executing multiple pre-planned tasks in parallel (e.g., production readiness waves), use `/batch-pipeline` instead of driving phases manually. The batch pipeline preserves critical infrastructure while skipping redundant phases.

### Why batch-pipeline exists

The full `/pipeline` (Plan → Plan Validation → Build → Review → Final Gate → Ship → Deploy → Reflect) is designed for new work that needs classification and planning. Pre-planned batch work (where the architect output already exists as a document) can skip Plan and Plan Validation, but **must not skip** state tracking, scratchpad, session memory, or the learning loop.

### What the orchestrator must NOT do for batch work

- Spawn build agents directly without creating pipeline state first
- Skip review (code-review + security-review are always mandatory)
- Skip the Reflect step (observations, session memory, cleanup)
- Drive phases manually without state file tracking
- Forget to inject session memory, scratchpad, and instincts into agent prompts

### What changes vs single-task pipeline

| Aspect | Single task | Batch |
|--------|-------------|-------|
| Entry point | `/intake` → `/pipeline` | `/batch-pipeline` |
| Plan phase | Architect designs | Already done (plan document) |
| Plan validation | User or challengers approve | Already approved |
| Build dispatch | 1 agent or team | N agents in parallel |
| Review dispatch | Team (persistent reviewers) | Subagents (parallel, per-task) |
| Final Gate | verify + test + accept team | Skipped (batch items are typically small) |
| State tracking | Same | Same (one state file per batch) |
| Scratchpad | Same | Shared across all batch agents |
| Observations | Same | One observation per batch |

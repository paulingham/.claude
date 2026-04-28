# Parallel Dispatch Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/parallel-dispatch-details.md`

## Hybrid Dispatch Model

The pipeline uses two dispatch mechanisms:

| Mechanism | When | Visibility | Cost |
|-----------|------|-----------|------|
| **Subagent** (Agent tool) | Plan, Ship, Deploy, single-slice Build | None (background) | Low (ephemeral) |
| **Team** (TeamCreate) | Plan Validation (autonomous), Multi-slice Build, Review, Final Gate | Tmux split panes | Higher (persistent sessions) |

> **Main-branch invariant.** All teammates and subagents commit to feature branches via worktrees, never to `main` in REPO_ROOT. Every HEAD-mutating git command MUST be expressed as `git -C "$WORKTREE" ...` or `(cd "$WORKTREE" && ...)`. Bare forms like `git checkout foo` and `gh pr create` are blocked by the `main-branch-guard.sh` PreToolUse hook regardless of caller cwd. REPO_ROOT HEAD must read `main` at every observation point. See `rules/agent-protocol.md > ## Main-Branch Invariant` for the canonical forbidden/allowed surface and the enforcement hooks.

## Team Phases

### Plan Validation Team (ALL pipelines)

| Scenario | Teammates | Parallel? |
|----------|-----------|-----------|
| Interactive mode | No team (user reviews) | N/A |
| Autonomous mode | product-reviewer (plan-reviewer) + software-engineer (plan-engineer) | Yes |

Key advantage: challengers **remember the plan context** on re-review — no prompt reconstruction needed.
Shut down both challengers after plan validation completes.

**HARD SEQUENCING REQUIREMENT** (hooks and prompt quality both matter):

1. Write the pipeline state file (`pipeline-state/{task-id}-pipeline.md`) **before** spawning any challenger.
   `pipeline-state-guard.sh` blocks write-capable agents when no state file exists — spawning challengers before creating the state file causes them to be blocked and report 0 tool uses.
2. The `software-engineer` plan challenger **must** be spawned with `isolation: "worktree"`.
   `agent-skill-reminder.sh` blocks write-capable agents without worktree — the challenger will be blocked and silently finish with 0 tool uses otherwise. `product-reviewer` is read-only and does not require worktree.
3. **Every challenger prompt must include the plan file path** (e.g., `pipeline-state/{task-id}-plan.md`) and an explicit instruction to read it.
   Without a file path, agents infer their verdict from prompt text alone and finish with 0 tool uses — this applies to **all** agent types, not just software-engineer. A product-reviewer or any other read-only agent will also skip tool use if the prompt gives them nothing to read.

**Diagnosing 0-tool-use challengers**:
- Both challengers show 0 tool uses → most likely a prompt quality issue (missing file path). Hook blocks would only affect software-engineer, not product-reviewer.
- Only software-engineer shows 0 tool uses → likely blocked by `agent-skill-reminder.sh` (no worktree) or `pipeline-state-guard.sh` (no state file).
- Do NOT respawn with changed isolation without first verifying the state file exists and the prompt references the plan file path.

### Build Team (conditional -- multi-slice or multi-domain only)

| Scenario | Teammates | Parallel? |
|----------|-----------|-----------|
| Single slice | Subagent (no team) | N/A |
| Multi-slice (independent ACs) | N engineers (1 per slice) | Yes |
| Multi-domain (API + UI + DB) | backend-eng + frontend-eng + db-eng | Yes |
| Best-of-N tagged (`bestofn:true` from intake) | Best-of-N variant — see below | Yes |

Shut down all engineers after build completes and branches are merged.

### Planning Agent (advisory — multi-slice Build only)

A long-lived Sonnet 4.6 `planning-agent` teammate is spawned **alongside** Build engineers when `slice_count >= 2`. It polls the pipeline scratchpad for findings that contradict the active plan, appends `## Plan Update` sections to `pipeline-state/{task-id}-plan.md`, and broadcasts `plan_update` messages to active build teammates.

**Single-slice Build path is UNCHANGED.** When `slice_count < 2`, no planning-agent is spawned and existing single-slice dispatch logic is unmodified.

| Direction | Message Type | Semantics |
|-----------|-------------|-----------|
| orchestrator → planning-agent | `plan_update_request` | optional nudge: re-scan now |
| orchestrator → planning-agent | `shutdown_request` | terminate after current cycle |
| planning-agent → each build teammate | `plan_update` | advisory broadcast; teammate may ignore mid-cycle |

**Verdicts**: `PLAN_REFINED` (≥1 plan update appended) or `PLAN_UNCHANGED` (no contradictions found). Both are acceptable — planning is advisory and never gates Build completion.

**Cost**: Sonnet 4.6 only. Never tunable up. ~$0.05/build typical.

See `skills/continuous-planning/SKILL.md` for the full procedure and contradiction rubric.
See `hooks/_lib/should_spawn_planning_agent.py` for the spawn-gate predicate.

### Best-of-N Build Team (conditional — `bestofn:true` from intake)

When `/intake` has tagged the task `bestofn: true` (computed in Step 2d-bis as `critical OR (task_class=="feature" AND Budget>=5)`), the Build phase dispatches as a Team variant that runs the same slice across N candidate models in parallel and picks the best output. This is NOT a separate skill — it is a dispatch mode of the Build Team. The winner still faces the normal Review → Final Gate → Ship gates; scoring selects *which* candidate faces those gates, it does not substitute for them.

**Procedure:**

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
   - `diff_size`: tie-breaker only
   - Composite: `test_pass*1000 + shape_compliance*100 + subjective_quality*20 - (diff_size/100)`
   - Ties break by smaller diff, then cheaper tier (sonnet < opus < external-frontier, integer ranks 1/2/3)
   - Reviewer MUST write a `## Selection Rationale` section — copied verbatim to the scratchpad for future `/learn` runs.
6. **Merge & cleanup**:
   - `git merge --no-ff build/{task-id}-boN-{winner-slug}` into the pipeline's working branch
   - For every loser: `git worktree remove --force <path>` then `git branch -D build/{task-id}-boN-{slug}`
   - Write `pipeline-state/{task-id}-best-of-n.md` (frontmatter: task_id, phase=build, verdict=BEST_OF_N_COMPLETE, timestamp; sections: Candidates Run, Winner, Selection Rationale, Cost Estimate Per Candidate)
   - Append `category: decision` note to `pipeline-state/{task-id}-scratchpad/best-of-n-selection.md`
7. **Winner proceeds to standard Review** — Best-of-N does not skip review or any subsequent gate.

**Fallback**: on `BEST_OF_N_FAILED` (insufficient candidates or all candidates failed their own tests), fall back to the standard single-engineer Build dispatch. Log the fallback in pipeline state under `## Re-routes`. Never halts.

**Helpers** (orchestrator-side, not skills):
- `skills/best-of-n/config.json` — roster, selection weights, tie-breaker order
- `skills/best-of-n/lib/score.sh` — sourceable pure-bash `score_candidate`, `pick_winner`, `check_budget_gate`
- `skills/best-of-n/external-runner.sh` — extension point for non-Anthropic candidates (honest stub today)
- `skills/best-of-n/tests/test_best_of_n.sh` — deterministic test of scoring, cleanup, and budget gate

### Review Team (always)

| Teammate | When | Pairing |
|----------|------|---------|
| code-reviewer | Always | executor: sonnet, advisor: opus (intended default — currently advisory) |
| security-engineer | Always | executor: sonnet, advisor: opus (intended default — currently advisory) |
| fix-engineer | Spawned into team on CHANGES_REQUESTED, shut down after fix | inherits from role |

Key advantage: reviewer **remembers the codebase** on re-review -- no context reconstruction. On CHANGES_REQUESTED, spawn fix-engineer into the same team, then re-assign review task to the raising reviewer (still alive, still has context).

**Advisor-mode cost** (PROVISIONAL pending advisor-baseline run; see `eval/baselines/{latest}-advisor-baseline.md`): Sonnet+Opus-advisor pairing is roughly ~40% cheaper per review than naive Opus-solo, with quality-equivalence (≥95% verdict-agreement) targeted but not yet measured. Hook (`pre-agent-advisor.sh`) is log-only today — see `rules/thinking-defaults.md` for the parallel Path B status.

### Final Gate Team (always)

Four phases run simultaneously instead of sequentially. All four are read-only against the same final state — no lock contention, no shared write surface.

| Teammate | Skill | Verdict |
|----------|-------|---------|
| qa-engineer (verify) | `/verify` | VERIFIED |
| qa-engineer (test) | `/qa-test-strategy` | COVERED |
| product-reviewer | `/product-acceptance` | APPROVED |
| patch-critic | `/patch-critique` | PATCH_APPROVED |

`patch-critic` evaluates the candidate patch by **test results + diff** — NOT SOLID/DRY (that is the code-reviewer's job, gated upstream). Inspired by SWE-bench top scaffolds (Agentless, AutoCodeRover, MarsCode-Agent) where a critic step distinguishes high-scoring patches from regressions. Rubric: tests cover the change, diff minimal vs spec, no obvious regressions visible from diff, no incidental refactor. PATCH_REJECTED returns to fix-engineer per `rules/pipeline-protocol.md` § In-Cycle Fix Rule — never escalates to the user.

All four assess the same final state independently. Shut down after all verdicts collected.

## Subagent Phases (unchanged)

| Phase | Why subagent |
|-------|-------------|
| Plan | Read-only, fast, single output |
| Ship | Simple PR creation |
| Deploy | Sequential deploy steps |

## Team Lifecycle

1. `TeamCreate("pipeline-{task-id}")` at pipeline start
2. Spawn teammates just-in-time when their phase begins
3. `TaskCreate` to define work, assign to teammates
4. Teammates read skill files, work, mark tasks complete, go idle
5. `SendMessage({type: "shutdown_request"})` to teammates when phase ends
6. Delete team after pipeline completes

## Resource Bounds

The harness bounds subagent recursion and per-job wall-clock time at the hook
layer. Two PreToolUse hooks enforce caps; a SubagentStop hook cleans up
runtime tracking.

**Caps (defaults; configurable via `settings.json` env block):**

| Bound | Default | Env override |
|-------|---------|--------------|
| Subagent recursion depth | 3 | `CLAUDE_SUBAGENT_MAX_DEPTH` |
| Subagent wall-clock | 1800s | `CLAUDE_SUBAGENT_MAX_RUNTIME` |
| Teammate wall-clock | 3600s | `CLAUDE_TEAMMATE_MAX_RUNTIME` |

**Hooks:**

- `hooks/depth-guard.sh` (PreToolUse Agent) — refuses spawn when
  `CLAUDE_SUBAGENT_DEPTH >= max`. Logs to
  `metrics/$SID/depth-violations.jsonl` with `record_type:"depth_violation"`,
  `depth`, `max_depth`, `subagent_type`, `task_id`, `action:"prevented"`.
- `hooks/runtime-guard.sh` (PreToolUse Agent|Bash|Write|Edit; Read
  intentionally excluded — highest-volume, fast-bounded). Mode A on Agent
  tool calls writes an idempotent
  `metrics/$SID/subagent-runtimes/<key>.start` file with
  `<unix_ts>:<class>:<display>`. Mode B on Bash|Write|Edit performs an
  orchestrator-level **global scan** of all start files and emits a shutdown
  directive on stderr (exit 2) for any over-cap entry. Logs to
  `metrics/$SID/runtime-violations.jsonl`.
- `hooks/subagent-stop-trajectory.sh` — extended with start-file cleanup on
  SubagentStop. Shared key derivation via `_lib/runtime-guard-key.sh`
  ensures the cleanup unambiguously targets the just-stopped agent.

**Shutdown semantics (Path-B disclosure):**

- **Teammate** (`team_name` set on the spawn): stderr block contains the
  exact `SendMessage({type:"shutdown_request", name:"<display>"})` form.
  Directly actionable per `rules/agent-protocol.md` § Teammate Lifecycle.
- **Non-team subagent**: out-of-band kill is not currently exposed by the
  Agent tool input schema. The stderr block surfaces the violation; the
  next tool the runaway subagent attempts is refused (PreToolUse exit 2);
  the orchestrator interprets the log and re-dispatches per
  `rules/operational-protocol.md` (retry-twice-then-escalate). Mirrors the
  `pre-agent-thinking.sh` Path-B precedent — a degraded-but-correct
  enforcement today, single-file flip when the API surface lands.

**Depth propagation:** the orchestrator sets `CLAUDE_SUBAGENT_DEPTH =
parent_depth + 1` in the shell that invokes Agent before each spawn. The
child subagent inherits the variable through its process env. See
`orchestrator/agent-orchestration.md > § Spawn Procedure` and
`orchestrator/parallel-dispatch-details.md > § Team Dispatch` for the
literal example bash assignment that orchestrators copy on each spawn.

## Teammate Prompt Template

> **Set `CLAUDE_SUBAGENT_DEPTH` in the spawn shell** (not as a prompt token —
> as an actual env var) so `depth-guard.sh` can enforce the recursion cap.
> See `orchestrator/agent-orchestration.md > § Spawn Procedure` and
> `orchestrator/parallel-dispatch-details.md > § Team Dispatch` for the
> exact `CLAUDE_SUBAGENT_DEPTH=<N>` shell assignment example.

```
Read the skill file at ~/.claude/skills/[name]/SKILL.md and execute it fully.
Also read ~/.claude/skills/[stack]-patterns/SKILL.md for tech-specific guidance if it exists.
Read ~/.claude/agents/[role].md for your full role definition, checklist, and output format.

Context:
- Team: pipeline-{task-id}
- Branch: [branch name]
- Base branch: [main/master]
- Changed files: [from git diff --name-only]
- Full diff: [single git diff output] (review phases only)
- Prior verdict: [previous phase verdict]
- Tech stack: [from project CLAUDE.md]
- Subagent depth: {N}

## Learned Patterns (from system learning)
[instincts filtered by role — top 5 by confidence; selection contract in `rules/autonomous-intelligence.md` § Instinct Injection]

## Session Context (engineering notes for this project)
[session memory content — full or priority sections by role]

## Pipeline Scratchpad (findings from prior agents)
[relevant findings from pipeline-state/{task-id}-scratchpad/]

Before completing, write any noteworthy discoveries to:
pipeline-state/{task-id}-scratchpad/{your-role}-{phase}.md

**Continuous Planning:** A `planning-agent` teammate may append `## Plan Update — <ISO>` sections to `pipeline-state/{task-id}-plan.md` while you work. Before starting each new behavior in your TDD cycle, re-read the plan file and check for `## Plan Update —` sections with timestamps newer than your spawn time. If you receive a `SendMessage` of type `plan_update`, finish your current RED-GREEN-REFACTOR cycle first, then re-read before starting the next behavior. Do not abandon a cycle in flight.

Emit `[CHECKPOINT] <marker>` lines on stdout at key milestones so the orchestrator can wait on them with `scripts/await-pattern.sh`. See the Checkpoint Vocabulary below for standard markers.
```

## What This Protocol Is NOT

- **NOT permission to skip skills.** Teammates must read and execute the full skill file.
- **NOT a reason to keep teammates alive across phases.** Shut down after phase completes.
- **NOT a shortcut.** Spawning teammates without skill file references is an anti-pattern.

## Why Hybrid

- **Teams** where parallelism or visibility adds value: Build (multi-slice), Review (parallel + re-review memory), Final Gate (3 phases at once)
- **Subagents** where fire-and-return is sufficient: Plan (quick), Ship (simple), Deploy (sequential)
- **Cost-conscious**: Idle teammates burn tokens. Only team up where it pays off.

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

## Checkpoint Vocabulary

Standard checkpoint markers for `[CHECKPOINT] <marker>` lines emitted on stdout. The orchestrator uses `scripts/await-pattern.sh` to block until these appear.

| Marker | Meaning |
|--------|---------|
| `[CHECKPOINT] build-started` | Teammate has begun implementation |
| `[CHECKPOINT] tests-green` | All tests passing; build complete |
| `[CHECKPOINT] tests-failed` | Tests failing; will not proceed |
| `[CHECKPOINT] review-started` | Reviewer has begun reviewing |
| `[CHECKPOINT] review-complete` | Review finished (check verdict separately) |
| `[CHECKPOINT] branch-pushed` | Feature branch pushed to remote |
| `[CHECKPOINT] pr-ready` | PR created and ready for review |
| `[CHECKPOINT] deploy-healthy` | Deployment passed health checks |
| `[CHECKPOINT] deploy-failed` | Deployment failed or rolled back |
| `[CHECKPOINT] task-complete` | All assigned work complete |

**Usage by orchestrator:**

```bash
scripts/await-pattern.sh "$teammate_log" '\[CHECKPOINT\] tests-green' 1800 100000
```

**Usage by teammate** (emit from build scripts or echo at phase boundaries):

```bash
echo "[CHECKPOINT] tests-green"
```

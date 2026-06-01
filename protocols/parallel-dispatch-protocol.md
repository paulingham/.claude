# Parallel Dispatch Protocol

Detailed orchestrator procedures: see `~/.claude/orchestrator/parallel-dispatch-details.md`

## Dispatch Model (parallel subagents by default; teams opt-in)

The pipeline uses **parallel subagent calls in a single message** as the default for every parallelizable phase. Tmux-visible teams (TeamCreate) are an opt-in mode for human-observable runs only — they are not required for correctness.

| Mechanism | When | Visibility | Activation |
|-----------|------|-----------|------------|
| **Subagent** (Agent tool) | All phases by default — parallel calls in a single message for parallelizable phases (Build multi-slice, Review, Final Gate, Plan Validation heavy) | None (background) | Always available |
| **Team** (TeamCreate) | Same phases when human visibility is desired | Tmux split panes | Opt-in via `CLAUDE_VISIBLE_TEAMS=1` env var, `/harness:pipeline --visible` flag, or interactive mode where the user requested it |

The dispatch matrix below describes *which roles run in parallel*; the *mechanism* is parallel subagents unless the visible-teams flag is set. Persistent reviewer context across re-review rounds (the historical reason teams were the default) is preserved by re-dispatching the same `subagent_type` with the original finding + fix diff in the prompt — context is in the spawn prompt, not in a long-lived process.

### When teams ARE worth it (visible mode only)

Tmux-visible teams remain the right choice when ANY of these is true:
- A human user is actively watching the run and wants to inspect mid-flight
- The pipeline is in interactive mode AND the user requested visibility
- Long-running multi-slice Build where a human wants to drop into a pane

In every other case (including all autonomous runs), parallel subagent calls are equivalent in correctness and cheaper in tokens because no idle teammates burn context between assignments.

> **Main-branch invariant.** All teammates and subagents commit to feature branches via worktrees, never to `main` in REPO_ROOT. Every HEAD-mutating git command MUST be expressed as `git -C "$WORKTREE" ...` or `(cd "$WORKTREE" && ...)`. Bare forms like `git checkout foo` and `gh pr create` are blocked by the `main-branch-guard.sh` PreToolUse hook regardless of caller cwd. REPO_ROOT HEAD must read `main` at every observation point. See `rules/agent-protocol.md > ## Main-Branch Invariant` for the canonical forbidden/allowed surface and the enforcement hooks.

## Team Phases

### Plan Validation Team

| Scenario | Teammates | Parallel? |
|----------|-----------|-----------|
| Interactive mode | No team (user reviews) | N/A |
| Autonomous mode + heavy gate (`critical OR Budget >= 7`) | product-reviewer + software-engineer challengers | Yes |
| Autonomous mode + light gate (everything else) | No team — invoke `/harness:plan-self-validation` | N/A |

Heavy-team challengers remember the plan context on re-review — no prompt reconstruction. The light branch is a single skill invocation. See `skills/plan-self-validation/SKILL.md`. Orchestrator dispatch procedure (HARD SEQUENCING REQUIREMENT, 0-tool-use diagnostics, isolation rules) lives in `~/.claude/orchestrator/parallel-dispatch-details.md` § Plan Validation Phase Dispatch.

### Build Team

| Scenario | Teammates | Parallel? |
|----------|-----------|-----------|
| Single slice | Subagent (no team) | N/A |
| Multi-slice (independent ACs) | N engineers (1 per slice) | Yes |
| Multi-domain (API + UI + DB) | backend-eng + frontend-eng + db-eng | Yes |
| Best-of-N tagged (`bestofn:true` from intake) | Best-of-N variant | Yes |

Orchestrator dispatch procedure lives in `~/.claude/orchestrator/parallel-dispatch-details.md` § Build Phase Dispatch. The Best-of-N variant (full N-candidate procedure: pre-flight worktree-capacity check, candidate roster, scoring rubric, merge & cleanup) lives there as the canonical Best-of-N reference.

### Planning Agent (advisory — multi-slice Build only)

A long-lived Sonnet 4.6 `planning-agent` teammate is spawned **alongside** Build engineers when `slice_count >= 2`. It polls the pipeline scratchpad for findings that contradict the active plan, appends `## Plan Update` sections to `pipeline-state/{task-id}-plan.md`, and broadcasts `plan_update` messages to active build teammates. Single-slice Build path is unchanged (no planning-agent spawned).

| Direction | Message Type | Semantics |
|-----------|-------------|-----------|
| orchestrator → planning-agent | `plan_update_request` | optional nudge: re-scan now |
| orchestrator → planning-agent | `shutdown_request` | terminate after current cycle |
| planning-agent → each build teammate | `plan_update` | advisory broadcast; teammate may ignore mid-cycle |

**Verdicts**: `PLAN_REFINED` (≥1 plan update appended) or `PLAN_UNCHANGED`. Planning is advisory and never gates Build completion. See `skills/continuous-planning/SKILL.md` for the contradiction rubric. Orchestrator spawn condition and dispatch detail live in `~/.claude/orchestrator/parallel-dispatch-details.md` § Planning Agent Dispatch.

### Review Team (always)

| Teammate | When | Pairing |
|----------|------|---------|
| code-reviewer | Always | executor: sonnet, advisor: opus (intended default — currently advisory) |
| security-engineer | Always | executor: sonnet, advisor: opus (intended default — currently advisory) |
| fix-engineer | Spawned into team on CHANGES_REQUESTED, shut down after fix | executor: opus, advisor: none (see `agents/fix-engineer.md`) |

Key advantage: reviewer **remembers the codebase** on re-review -- no context reconstruction. On CHANGES_REQUESTED, spawn `fix-engineer` (see `agents/fix-engineer.md`) into the same team — fix-engineer reuses the prior build's worktree (NOT a fresh one) and operates with fix-cycle-specific guidance (verify finding validity first, no scope creep, no compliance commit messages). Then re-assign the review task to the raising reviewer (still alive, still has context).

**Advisor-mode cost** (PROVISIONAL pending advisor-baseline run; see `eval/baselines/{latest}-advisor-baseline.md`): Sonnet+Opus-advisor pairing is roughly ~40% cheaper per review than naive Opus-solo, with quality-equivalence (≥95% verdict-agreement) targeted but not yet measured. Hook (`pre-agent-advisor.sh`) is log-only today — see `rules/thinking-defaults.md` for the parallel Path B status.

### Final Gate Team (always)

Five phases run simultaneously instead of sequentially. All five are read-only against the same final state — no lock contention, no shared write surface (with one exception: `spec-blind-validator` writes test files to `tests/`, gated by `hooks/spec-blind-write-guard.sh`).

| Teammate | Skill | Verdict |
|----------|-------|---------|
| qa-engineer (verify) | `/harness:verify` | VERIFIED |
| qa-engineer (test) | `/harness:qa-test-strategy` | COVERED |
| product-reviewer | `/harness:product-acceptance` | APPROVED |
| patch-critic | `/harness:patch-critique` | PATCH_APPROVED |
| spec-blind-validator | `/harness:spec-blind-validate` | SPEC_BLIND_VALIDATED |

`patch-critic` evaluates the candidate patch by **test results + diff** — NOT SOLID/DRY (that is the code-reviewer's job, gated upstream). Inspired by SWE-bench top scaffolds (Agentless, AutoCodeRover, MarsCode-Agent) where a critic step distinguishes high-scoring patches from regressions. Rubric: tests cover the change, diff minimal vs spec, no obvious regressions visible from diff, no incidental refactor. PATCH_REJECTED returns to fix-engineer per `protocols/pipeline-protocol.md` § In-Cycle Fix Rule — never escalates to the user.

`spec-blind-validator` authors black-box behavioural tests from the AC plan + public API surface ONLY — never implementation source. Three PreToolUse hooks (`hooks/spec-blind-{read,write,bash}-guard.sh`) bind the spec-blind property at the tool layer, so the validator cannot fall back to `cat src/`/`node -e`/`grep -r src/` to reach internals. Verdicts: `SPEC_BLIND_VALIDATED` (success → next gate), `SPEC_BLIND_FAILED` (failure → fix-engineer code-fix-only; MUST NOT mutate ACs), `SPEC_BLIND_INSUFFICIENT_SURFACE` (info → next gate; Final Gate summary renders `spec-blind: SKIPPED (no public surface)`), `SPEC_BLIND_BLOCKED` (failure → HALT pipeline + operator escalation, no auto-advance, no fix-engineer dispatch). Inspired by SWE-Bench Pro vs Verified — closes the failure mode where build-time tests codify the same misconceptions about the spec as production code.

All five assess the same final state independently.

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
- `hooks/tool-timing-capture.sh` (PostToolUse + PostToolUseFailure) —
  appends one JSONL line per call to `metrics/$SID/tool-timings.jsonl`
  using the Claude Code 2.1.119+ `duration_ms` payload field. Capture
  vs. enforcement split: this hook owns capture; `runtime-guard.sh`
  owns enforcement. See `rules/agent-protocol.md` § Resource Bounds.

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
<!-- claude:persona-end -->

**Tool-result fabrication is forbidden.** If you do not actually receive a tool result back from the harness — empty content, missing tool block, error response with no payload — halt and report. Never fabricate or assume what the result would have been. Stale results from earlier in the session are not evidence. Re-invoke the tool if the failure mode warrants a retry; otherwise surface the missing result to the orchestrator and stop. (See https://github.com/anthropics/claude-code/issues/10628.)

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
[relevant findings from pipeline-state/{task-id}/scratchpad/]

Before completing, write any noteworthy discoveries to:
pipeline-state/{task-id}/scratchpad/{your-role}-{phase}.md

**Continuous Planning:** A `planning-agent` teammate may append `## Plan Update — <ISO>` sections to `pipeline-state/{task-id}-plan.md` while you work. Before starting each new behavior in your TDD cycle, re-read the plan file and check for `## Plan Update —` sections with timestamps newer than your spawn time. If you receive a `SendMessage` of type `plan_update`, finish your current RED-GREEN-REFACTOR cycle first, then re-read before starting the next behavior. Do not abandon a cycle in flight.

Emit `[CHECKPOINT] <marker>` lines on stdout at key milestones so the orchestrator can wait on them with `scripts/await-pattern.sh`. See the Checkpoint Vocabulary below for standard markers.
```

## What This Protocol Is NOT

- **NOT permission to skip skills.** Teammates must read and execute the full skill file.
- **NOT a reason to keep teammates alive across phases.** Shut down after phase completes.
- **NOT a shortcut.** Spawning teammates without skill file references is an anti-pattern.

## Why Subagents-by-Default

- **Subagents** are sufficient for correctness in every parallelizable phase. Parallel calls in a single message produce the same fan-out as a team without persistent processes.
- **Teams** add only one thing: human-observable parallelism via tmux panes. Useful when a person is watching, irrelevant when no one is.
- **Cost-conscious**: idle teammates burn context tokens between assignments. Default-off team mode reclaims that cost on every autonomous run.
- **Re-review memory** (the original reason teams were default) is reconstructed by re-dispatching the same `subagent_type` with the original finding plus the fix diff in the prompt. Context lives in the spawn prompt, not in a long-lived process — this works for both subagents and teammates.

## Batch Execution

For pre-planned batch work (production-readiness waves, bulk fixes), the entry point is `/harness:batch-pipeline` instead of `/harness:pipeline`. The batch pipeline skips Plan + Plan Validation but preserves state tracking, scratchpad, session memory, observations, and the mandatory Review step. Orchestrator-side rules (what must / must not be skipped, dispatch differences) live in `~/.claude/orchestrator/parallel-dispatch-details.md` § Batch Execution.

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

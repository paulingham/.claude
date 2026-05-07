# Nested-Pipeline Isolation Contract

Canonical reference for the environment-variable contract that lets an **inner** `/pipeline` (spawned from within an **outer** pipeline — e.g. by the `/internal-eval` harness running a case via `run-case.sh`) execute without colliding with the outer pipeline on shared state.

## Invariant

**No env vars set = current behavior unchanged.** Every consumer hook MUST gracefully degrade to its pre-isolation behavior when the variables below are unset. The isolation contract is purely opt-in; the outer pipeline (and all ad-hoc use) continues to work exactly as before.

## Contract

| Variable | Default | Purpose | Consumer hook(s) |
|---|---|---|---|
| `CLAUDE_PIPELINE_TASK_ID` | (auto-detected from `pipeline-state/*-pipeline.md`) | Force the pipeline id the trajectory recorder namespaces to. Skips filesystem scan. | `hooks/subagent-stop-trajectory.sh`, `hooks/observation-capture.sh` (phase detection), TeamCreate naming (orchestrator-side) |
| `CLAUDE_PIPELINE_BYPASS` | `0` | When `1`, the pipeline-state-guard PreToolUse hook allows write-capable agent spawns without an active outer-pipeline state file. Emits `[guard] bypass: EVAL_RUN_ID=... EVAL_CASE_ID=...` to stderr for auditability. | `hooks/pipeline-state-guard.sh` |
| `CLAUDE_DISABLE_AUTO_LEARN` | `0` | When `1`, the auto-learn gate Stop hook fast-exits. Prevents inner pipelines from polluting the outer's learn cadence. | `hooks/auto-learn-gate.sh` |
| `CLAUDE_PROJECT_HASH` | (computed via `_project_hash`) | Explicit project-hash override. Redirects observations + session memory to an isolated namespace. | `hooks/observation-capture.sh`, session-memory resolution (via shared `$HOME`) |
| `EVAL_RUN_ID` | (unset) | Tags cost records with the run id. When BOTH `EVAL_RUN_ID` AND `EVAL_CASE_ID` are set, cost records gain two extra JSON keys. | `hooks/cost-tracker.sh` |
| `EVAL_CASE_ID` | (unset) | Tags cost records with the case id. See `EVAL_RUN_ID`. | `hooks/cost-tracker.sh` |
| `HOME` / `CLAUDE_HARNESS_ROOT` | `$HOME` | Shadow-root. The inner pipeline may set `HOME` to a scratch directory so skill, hook, and rule resolution reads from a different `.claude/` tree entirely. `CLAUDE_HARNESS_ROOT` is reserved for Story 7's finer-grained shadowing when the shell can't be fully re-rooted. | All file-based resolution |

## Collision Surfaces Addressed

Without this contract, inner and outer pipelines collide on:

1. **pipeline-state** — both write to `~/.claude/pipeline-state/{task-id}/pipeline.md` (canonical) or `~/.claude/pipeline-state/*-pipeline.md` (legacy, read-tolerated during 90-day DUAL_PATH soak). `CLAUDE_PIPELINE_BYPASS=1` lets the inner proceed without a state file of its own in the outer's directory; `HOME` isolation gives it its own directory entirely.
2. **scratchpad** — `pipeline-state/{task-id}/scratchpad/` (canonical; legacy: `pipeline-state/{task-id}-scratchpad/`). Same mitigation as (1).
3. **trajectory** — `pipeline-state/{task-id}/trajectory.jsonl` (canonical; legacy: `pipeline-state/{task-id}-trajectory.jsonl`). `CLAUDE_PIPELINE_TASK_ID` forces the namespace.
4. **observations** — `learning/{project-hash}/observations.jsonl`. `CLAUDE_PROJECT_HASH` redirects.
5. **learning/instincts** — `learning/{project-hash}/instincts/`. Same as (4).
6. **session-memory** — `session-memory/{project-hash}/{sub-file}.md` (5 sub-files: `codebase-map`, `build-test`, `patterns`, `fragility`, `active-work`). Respects `HOME` + `CLAUDE_PROJECT_HASH`. Legacy single-file form still readable via `session_memory_read_split` during the 30-day DUAL_PATH soak.
7. **cost records** — `metrics/costs.jsonl`. `EVAL_RUN_ID` + `EVAL_CASE_ID` let a post-run aggregator filter records belonging to one eval run.
8. **TeamCreate naming** — orchestrator-side concern; consumers of `CLAUDE_PIPELINE_TASK_ID` derive their team name from it.
9. **pipeline-state-guard enforcement** — `CLAUDE_PIPELINE_BYPASS=1` opts out.

## Kill-Mid-Run Guarantee

If an inner pipeline is killed part-way through, the outer pipeline-state directory must contain **zero** inner residue (no `eval-{run-id}-*` files). This is enforced by construction: when the inner pipeline uses `HOME` isolation, it writes to its own `pipeline-state/` directory entirely; the outer's is never touched. When the inner only uses `CLAUDE_PIPELINE_BYPASS=1` without a shadow `HOME`, it must not create any `pipeline-state/` files of its own — the bypass is exactly the promise that it won't.

## Consumer-Side Implementation Notes

- Every consumer hook MUST check the variable with a `${VAR:-default}` expansion — never assume it is set.
- The `no env vars set = unchanged` invariant is covered by a regression test in `hooks/tests/test-nested-pipeline-isolation.sh`. Any consumer patch that breaks that test is rejected.
- Future additions to this contract MUST be added to the table above AND given a regression test in the same file.

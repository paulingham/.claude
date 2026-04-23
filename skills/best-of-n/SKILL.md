---
name: "best-of-n"
description: "Critical-path build strategy: run the same slice across N parallel frontier models (best of n, multi-model bake-off, parallel models), diff outputs, score on test_pass + shape + subjective quality, merge the winner. Invoke only for Build phase when /intake tagged the task `critical` AND Complexity Budget >= 7 — e.g. payment, auth, security, cross-repo contract, or production-blocking bug. Not the default build path; standard work uses /build-implementation."
model: opus
argument-hint: "Slice spec + ACs for the critical-path build"
---

# Best-of-N Build

## What This Skill Does

Dispatches one build agent per candidate model from a configured roster in parallel, each on its own branch. Collects test results, shape violations, diff size, and subjective quality, then has a single code-reviewer score the candidates against a rubric and pick a winner. The winner's branch is merged into the pipeline's working branch; loser branches and worktrees are cleaned up. The rationale is persisted to pipeline state and scratchpad so future runs and `/learn` can see which candidate won and why.

## When To Invoke

- `/pipeline` routes here during the Build phase when the intake state flags `critical: true` AND Complexity Budget >= 7.
- Manual invocation by the orchestrator for a deliberately critical-path slice.
- **NOT the default.** All other Build work uses `/build-implementation`. Do not change that skill.

## Dispatch Mode

Invoked by the orchestrator via the Skill tool. This skill itself orchestrates multiple `software-engineer` (or `frontend-engineer`) subagent spawns in parallel worktrees. It does NOT execute code in the orchestrator process — it describes the dispatch to the orchestrator.

## Procedure

### Step 0: Cost Gate (Hard Early-Exit)

Read Complexity Budget from `pipeline-state/{task-id}-intake.md` frontmatter (or from the orchestrator's prompt if provided there).

If Budget < `min_complexity_budget` (default 7):

```
VERDICT: WRONG_SKILL
REASON: Complexity Budget {N} below threshold 7 — use /build-implementation
```

Return immediately. No dispatch, no roster load.

### Step 1: Load Config

Read `~/.claude/skills/best-of-n/config.json`. List `default_roster` entries. Respect `max_candidates` as an upper bound.

### Step 2: Validate Candidates

For each candidate:
- If `required_env` is non-null, check the env var is set in the orchestrator's environment.
- If missing, emit `[best-of-n] Skipping {slug}: {required_env} not set` and drop the candidate.
- Keep only candidates that pass validation, subject to `max_candidates`.

If fewer than 2 candidates remain:
```
VERDICT: BEST_OF_N_FAILED
REASON: insufficient candidates ({N} available, 2 required)
```

### Step 3: Dispatch Engineers (Parallel)

Spawn one Agent per surviving candidate in a single orchestrator message. Template for Anthropic candidates (`provider == "anthropic"`):

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

For external candidates (`provider != "anthropic"`):

1. Check `skills/best-of-n/external-runner.sh` exists and is executable.
2. Call it with `--candidate-slug {slug} --task-id {task-id} --slice-spec-path {path} --branch build/{task-id}-boN-{slug} --required-env {required_env}`.
3. If it exits non-zero, log the runner's stderr as `[best-of-n] external candidate {slug} skipped: {message}` and drop the candidate. **Do NOT fabricate results.**
4. If it exits zero, it has committed to the candidate branch and printed the commit SHA on stdout — record it.

### Step 4: Collect Results

For every candidate that actually produced a branch, gather:

- `branch`: `build/{task-id}-boN-{slug}`
- `commit_sha`: from the branch tip
- `test_pass`: 1 if the full test suite is green on that branch, else 0
- `shape_violations`: run `hooks/code-shape-check.sh` across files changed on the branch, count violations
- `diff_size`: integer from `git diff --stat main..<branch> | tail -1 | awk '{print $4+$6}'` (insertions+deletions; 0 if empty)

### Step 5: Spawn Reviewer (Selection)

Spawn ONE code-reviewer teammate in the pipeline team. Include all N diffs, test results, and shape counts. The reviewer's rubric:

- `test_pass`: 1 if all tests green else 0
- `shape_compliance`: `max(0, 1 - violations/10)`
- `subjective_quality`: reviewer's 1-5 score on clarity + correctness, with prose justification
- `diff_size`: tie-breaker only

Composite:

```
score = test_pass*1000 + shape_compliance*100 + subjective_quality*20 - (diff_size/100)
```

Ties break by: smaller `diff_size`; then cheaper tier (sonnet < opus < external-frontier, mapped to integer ranks 1, 2, 3).

Reviewer MUST write a `## Selection Rationale` section (winner slug, brief justification per candidate, the composite score table). This section is copied verbatim to the scratchpad in Step 6.

### Step 6: Merge & Cleanup

With the winner decided:

1. `git merge --no-ff build/{task-id}-boN-{winner-slug}` into the pipeline's working branch.
2. For every loser slug:
   - `git worktree remove --force <worktree-path>` (if a worktree exists for that candidate)
   - `git branch -D build/{task-id}-boN-{slug}`
3. Write `pipeline-state/{task-id}-best-of-n.md` with this frontmatter and sections:

```markdown
---
task_id: {task-id}
phase: build
verdict: BEST_OF_N_COMPLETE
timestamp: {ISO 8601}
---

## Candidates Run
| slug | provider | model_id | tests | shape_violations | diff_size | composite |
|------|----------|----------|-------|------------------|-----------|-----------|

## Winner
{slug} — commit {sha}

## Selection Rationale
> {quoted rationale from reviewer}

## Cost Estimate Per Candidate
| slug | input_mtok_est | output_mtok_est | cost_est_usd |
|------|----------------|-----------------|--------------|
```

4. Append to `pipeline-state/{task-id}-scratchpad/best-of-n-selection.md`:

```markdown
---
category: decision
---

Best-of-N winner: {slug}. Beat {loser-count} candidates on composite={score}.
Rationale: {one-line summary from reviewer}.
```

### Verdicts

- `BEST_OF_N_COMPLETE` — winner merged, losers cleaned up, state file written.
- `BEST_OF_N_FAILED` — insufficient candidates after validation, or all candidate agents returned failure. On this verdict the pipeline falls back to `/build-implementation`.
- `WRONG_SKILL` — Step 0 gate rejected (Budget < 7).

## Phase Output

```
Verdict: BEST_OF_N_COMPLETE | BEST_OF_N_FAILED | WRONG_SKILL
Next: Review phase (on success) | /build-implementation fallback (on failure) | /build-implementation (on WRONG_SKILL)
Artifacts: pipeline-state/{task-id}-best-of-n.md, merged winner branch, scratchpad selection note
```

## Anti-Patterns

- **Default build path.** Not used. Only fires on `critical: true` AND Budget >= 7. Do not bypass the gate.
- **Low-budget work.** Budget < 7 → return `WRONG_SKILL`. The 2-3x cost is not justified for small slices.
- **Fabricated external results.** If `external-runner.sh` returns non-zero, drop the candidate. Never invent a commit SHA or diff for an external model that did not actually run.
- **Skipping re-review.** The merged winner's branch still goes through normal `/code-review` and `/security-review` — Best-of-N selection is not a substitute for review.
- **Persisting worktrees.** Loser worktrees must be removed (`--force`) and loser branches deleted. Idle worktrees break later runs.

## Related

- `skills/best-of-n/config.json` — roster and weights.
- `skills/best-of-n/external-runner.sh` — extension point for non-Anthropic providers (currently a stub).
- `skills/best-of-n/lib/score.sh` — pure-bash scoring helpers (`score_candidate`, `pick_winner`, `check_budget_gate`).
- `skills/best-of-n/tests/test_best_of_n.sh` — integration test.
$ARGUMENTS

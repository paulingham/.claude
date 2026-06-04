---
name: best-of-n
description: "N-candidate parallel build with critic-selected winner. Procedure lives in orchestrator/parallel-dispatch-details.md; this file is the skill contract surface."
verdict: BoN_WINNER_SELECTED|BoN_FALLBACK_TO_SINGLE|BoN_INSUFFICIENT_RESOURCES
phase: build
dispatch: team
---

# Best-of-N

## When to Invoke

Routed by `/harness:pipeline` only when `/harness:intake` set `bestofn: true` (`critical OR [best-of-n]` user override). Never user-facing; never invoked directly. Standard Build dispatches are the default — this is a Build dispatch *mode*, not a substitute for Review or Final Gate.

## Inputs

- Slice spec at `$state_dir/{task-id}/plan.md` with per-AC failing-test stubs.
- Candidate roster from `skills/best-of-n/config.json` (Opus 4.7 + Sonnet 4.6 always; external slot via `required_env`).
- Pre-flight worktree-pool capacity (default cap 6 workstation / 12 CI; `CLAUDE_BESTOFN_MAX_WORKTREES`).

## Procedure

See `~/.claude/orchestrator/parallel-dispatch-details.md` § Best-of-N Build Team Dispatch.

## Output

- Pipeline state: `$state_dir/{task-id}/best-of-n.md` (frontmatter `verdict`, sections: Candidates Run, Winner SHA, Per-Candidate Scores, Selection Rationale, Total Cost USD via `cost_estimator`, Cluster Sizes — `N/A` until FMV is wired).
- Scratchpad: `$state_dir/{task-id}/scratchpad/best-of-n-selection.md` (`category: decision`) — always carries the verbatim Selection Rationale; additionally carries a divergence record with diff-stat + Jaccard when the top two candidates clear the Step 5 tie-breaker boundary AND have changed-files Jaccard < 0.5 (mining path: `observations.jsonl` → `/harness:learn` Step 3d, never direct scratchpad → anti-pattern). Tie-breaker source + spec: see orchestrator details § Best-of-N Step 5.
- Winner branch merged into the pipeline working branch; loser worktrees + branches removed.

## Verdict

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `BoN_WINNER_SELECTED` | ≥2 candidates produced green builds; reviewer picked one. | Winner proceeds to `/harness:code-review` + `/harness:security-review` (standard Review). |
| `BoN_FALLBACK_TO_SINGLE` | <2 valid candidates after validation/runs (e.g. external `required_env` unset, all but one failed own tests). Fallback is silent and logged in `## Re-routes`. | Single-candidate Build dispatch on the same slice. |
| `BoN_INSUFFICIENT_RESOURCES` | Pre-flight worktree-capacity check exceeded the cap. | Halt this dispatch; pipeline escalates to user (or falls back to single-engineer if policy permits). |

## Anti-Patterns

- Invoking on a non-critical task without the `[best-of-n]` user override — the 2-3x spend is not justified by baseline data.
- Running when the worktree pool is exhausted — must emit `BoN_INSUFFICIENT_RESOURCES`, never silently overcommit disk/inodes.
- Silent fallback to single-candidate without emitting `BoN_FALLBACK_TO_SINGLE` — every re-route must be auditable in pipeline state.

## Tests

`skills/best-of-n/tests/` holds scoring/selection coverage (`test_best_of_n.sh`). Structure-drift coverage lives at `scripts/test_best_of_n_skill_structure.sh`, which runs the canonical-template audit against this file.

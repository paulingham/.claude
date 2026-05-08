---
name: best-of-n
description: "N-candidate parallel build with critic-selected winner. Procedure lives in orchestrator/parallel-dispatch-details.md; this file is the skill contract surface."
verdict: BoN_WINNER_SELECTED|BoN_FALLBACK_TO_SINGLE|BoN_INSUFFICIENT_RESOURCES
phase: build
dispatch: team
---

# Best-of-N

## When to Invoke

Routed by `/pipeline` only when `/intake` set `bestofn: true` (`critical OR [best-of-n]` user override). Never user-facing; never invoked directly. Standard Build dispatches are the default — this is a Build dispatch *mode*, not a substitute for Review or Final Gate.

## Inputs

- Slice spec at `pipeline-state/{task-id}/plan.md` with per-AC failing-test stubs.
- Candidate roster from `skills/best-of-n/config.json` (Opus 4.7 + Sonnet 4.6 always; external slot via `required_env`).
- Pre-flight worktree-pool capacity (default cap 6 workstation / 12 CI; `CLAUDE_BESTOFN_MAX_WORKTREES`).

## Procedure

See `~/.claude/orchestrator/parallel-dispatch-details.md` § Best-of-N Build Team Dispatch.

Tie-breaker source: candidate diff cohesion — `(changed_files, changed_lines)` from the Step 4 `git diff --stat main..<branch>` capture, ordered ascending. Fires only when `subjective_quality` and `shape_compliance` are equal; falls through to executor-tier rank otherwise. Composite-tied candidates with non-overlapping file sets (Jaccard < 0.5) get a `category: decision` divergence finding written to `pipeline-state/{task-id}/scratchpad/best-of-n-selection.md` for downstream `/learn` Step 3d mining via the standard observations.jsonl path — never a direct scratchpad → anti-pattern shortcut.

## Output

- Pipeline state: `pipeline-state/{task-id}/best-of-n.md` (frontmatter `verdict`, sections: Candidates Run, Winner SHA, Per-Candidate Scores, Selection Rationale, Total Cost USD via `cost_estimator`, Cluster Sizes — `N/A` until FMV is wired).
- Scratchpad: `pipeline-state/{task-id}/scratchpad/best-of-n-selection.md` with `category: decision`.
- Winner branch merged into the pipeline working branch; loser worktrees + branches removed.

## Verdict

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `BoN_WINNER_SELECTED` | ≥2 candidates produced green builds; reviewer picked one. | Winner proceeds to `/code-review` + `/security-review` (standard Review). |
| `BoN_FALLBACK_TO_SINGLE` | <2 valid candidates after validation/runs (e.g. external `required_env` unset, all but one failed own tests). Fallback is silent and logged in `## Re-routes`. | Single-candidate Build dispatch on the same slice. |
| `BoN_INSUFFICIENT_RESOURCES` | Pre-flight worktree-capacity check exceeded the cap. | Halt this dispatch; pipeline escalates to user (or falls back to single-engineer if policy permits). |

## Anti-Patterns

- Invoking on a non-critical task without the `[best-of-n]` user override — the 2-3x spend is not justified by baseline data.
- Running when the worktree pool is exhausted — must emit `BoN_INSUFFICIENT_RESOURCES`, never silently overcommit disk/inodes.
- Silent fallback to single-candidate without emitting `BoN_FALLBACK_TO_SINGLE` — every re-route must be auditable in pipeline state.

## Tests

`skills/best-of-n/tests/` holds scoring/selection coverage (`test_best_of_n.sh`). Structure-drift coverage lives at `scripts/test_best_of_n_skill_structure.sh`, which runs the canonical-template audit against this file.

---
name: pdr-rtv
description: "Parallel-Diverse-Refine + Recursive-Tournament-Verification (arXiv:2604.16529). Build-phase dispatch variant that scales test-time compute via T=2 iterations of N parallel rollouts, summary-based refinement, and pairwise tournament selection. User-Intent Reconciliation: original spec located PDR-RTV at gate-time; chosen Build-phase placement is paper-aligned (the 70.9% → 77.6% Pass@1 lift comes from generating better candidate patches, not re-verifying one). Gate-time verification angle is covered by multi-persona patch-critic (#93). Procedure lives in orchestrator/parallel-dispatch-details.md."
verdict: PDR_WINNER_SELECTED|PDR_NO_CONSENSUS
phase: build
dispatch: team
---

# PDR-RTV

## When to Invoke

Routed by `/harness:pipeline` only when `/harness:intake` set `pdr_rtv: true` (`budget >= ${CLAUDE_PDR_RTV_BUDGET_FLOOR:-10} AND critical == true`). Mutually exclusive with Best-of-N — when both flags fire, PDR-RTV wins as the strictly stronger variant. Never user-facing.

## Inputs

- Slice spec at `pipeline-state/{task-id}/plan.md` with per-AC failing-test stubs.
- Candidate roster from `skills/pdr-rtv/config.json` (N, T, K, seed, max_runtime).
- Pre-flight worktree-pool capacity via `skills/best-of-n/lib/score.sh`'s `check_worktree_capacity` (peak concurrent worktrees = N = 4 due to strict iteration serialisation).

## Procedure

See `~/.claude/orchestrator/parallel-dispatch-details.md` § PDR-RTV Build Team Dispatch.

## Output

- Pipeline state: `pipeline-state/{task-id}/pdr-rtv.md` (frontmatter `verdict`, sections: Iterations, Tournament Bracket, Winner SHA, Total Cost USD, Re-routes if any).
- Per-rollout summaries: `pipeline-state/{task-id}/pdr-rtv/rollouts/{slug}/summary.md` (three required H2 sections; persists OUTSIDE worktrees so iteration-0 worktrees can be reaped before iteration-1).
- Tournament log: `pipeline-state/{task-id}/pdr-rtv/tournament.md` (Slice 2).
- Winner branch merged into the pipeline working branch; loser worktrees + branches removed.

## Verdict

| Verdict | Meaning | Downstream |
|---------|---------|------------|
| `PDR_WINNER_SELECTED` | Tournament elected a winner. | Winner proceeds to standard Review (`/harness:code-review` + `/harness:security-review`). |
| `PDR_NO_CONSENSUS` | <4 green builds across iterations, OR all finalists rejected, OR worktree-cap exceeded. | Silent fallback to Best-of-N → standard Build; logged in `## Re-routes` with `fallback_reason` enum. |

## Anti-Patterns

- Invoking when `bestofn == true AND pdr_rtv == false` — that path is Best-of-N's domain.
- Skipping iteration-0 worktree reaping before iteration-1 dispatch — peak worktrees would balloon to 2N.
- Relaxing the AND-clause trigger (e.g. reverting to `OR critical`, dropping the floor below 10, or removing the `critical == true` requirement) without `/harness:eval-model-effectiveness` showing ≥5% Pass@1 lift on the harness regression suite. The May 2026 narrowing (PR for pdr-rtv-trigger-tighten) shifted from `OR critical` to `AND critical == true` after cost forensics showed the OR-clause fired PDR-RTV (5.5–7.5× Build cost) on non-critical budget-9 work that did not warrant the spend. The conjunctive trigger is the current policy floor; any relaxation must be evidence-backed. Operators with stale `CLAUDE_PDR_RTV_BUDGET_FLOOR=N` env overrides should note the AND clause means the override interacts multiplicatively with the `critical` flag — both clauses must be true to fire.

## Tests

`skills/pdr-rtv/tests/` holds bats coverage for skill structure, distillation, and dispatch. Structure-drift audit lives at `scripts/test_pdr_rtv_skill_structure.sh`.

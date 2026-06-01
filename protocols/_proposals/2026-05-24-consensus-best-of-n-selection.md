# Proposal: Wire the Stubbed Consensus (FMV) Signal Into Best-of-N Selection

**Status:** PROPOSED (2026-05-24)
**Owner:** orchestrator-derived recommendation from external research (Majority-of-the-Bests; LLM-as-judge bias)
**Implementation track:** requires `/harness:pipeline` run (touches `skills/best-of-n/config.json`, selection logic in `orchestrator/parallel-dispatch-details.md` § Best-of-N Step 5, tests)

---

## Problem

Best-of-N selection is **already mostly execution-grounded** — `skills/best-of-n/config.json` weights `test_pass_bonus: 1000` far above `subjective_quality_bonus: 20`, and `tie_breaker_order` is objective (`changed_files_asc`, `changed_lines_asc`, `cost_asc`). This is the right shape and should be preserved.

The residual weakness is narrow but real: when ≥2 candidates **both pass all tests and both meet shape** (the common case for a well-specified slice), the only signals separating them are `subjective_quality_bonus` (a critic/LLM-judge score, weight 20) and diff-size. External 2026 evidence is specific about this regime:

- **LLM-as-judge degrades exactly here.** Judges show ~200% more inconsistency on *close* candidates, a strong positive/self bias, and a low true-negative rate (good at confirming, bad at rejecting). Gating a production winner on a judge score over near-identical green candidates is the weakest link. (arXiv 2512.16041, 2509.26072, 2510.11822.)
- **Consensus beats judging in this regime.** "Majority-of-the-Bests" (MoB) selects the *mode* of the candidate distribution and beats vanilla Best-of-N in 25/30 setups; self-certainty selection scales it cheaply. The principle: among execution-passing candidates, prefer the behaviour multiple independent generations *agree on*, not the one a judge *prefers*. (arXiv 2511.18630, 2502.18581.)

The harness has already scaffolded toward this: `best-of-n.md` output carries `Cluster Sizes — N/A until FMV is wired` and records a divergence entry with diff-stat + **Jaccard** when the top two candidates clear the tie-breaker boundary with changed-files Jaccard < 0.5. The clustering signal is designed; it just isn't computed or used in selection.

## Proposed Change

Wire the stubbed consensus signal and let it **replace the subjective-quality bonus in the tie regime only**:

1. Among candidates that have already cleared `test_pass_bonus` + `shape_compliance_bonus` (i.e. the green, shape-clean set), compute behavioural agreement — start with the cheapest viable proxy: cluster candidates by changed-files Jaccard ≥ 0.5 (the divergence record already computes the inputs) and, where a shared test harness exists, by identical pass/fail vectors on the union of all candidates' authored tests.
2. Add `consensus_bonus` to `selection_weights`, slotted **above** `subjective_quality_bonus` (e.g. `consensus_bonus: 60`, `subjective_quality_bonus: 20`). The largest agreement cluster wins; the critic score becomes the final tie-break *within* a single cluster, not the cross-candidate decider.
3. Populate `Cluster Sizes` in `best-of-n.md` with the computed cluster cardinalities (retire the `N/A` placeholder).
4. Keep `test_pass_bonus: 1000` dominant and the objective `tie_breaker_order` unchanged — consensus only ever arbitrates among already-green, already-shape-clean candidates.

## Expected Effect

- **Higher "verified-right, not just looks-right" hit rate** on the exact regime where it's been weakest: multiple plausible green diffs. Picking the behaviour two independent generations converged on is a stronger correctness prior than a single judge's preference.
- **Cheaper than escalating the judge.** Clustering reuses signals already computed (Jaccard, test vectors); no extra model spawn. It also reduces reliance on the `subjective_quality` critic pass, a minor token saving.
- No change to the common single-green-candidate case (consensus is a no-op when one candidate dominates on tests/shape).

## Why this is safe

1. **Execution gates stay authoritative.** `test_pass_bonus` (1000) still dwarfs `consensus_bonus` (60); a green candidate never loses to a red one, and consensus only orders *within* the green set.
2. **The signal is already designed and partially recorded** — this finishes a documented stub (`FMV`/`Cluster Sizes`/Jaccard), it does not invent a new mechanism.
3. **Reversible** — drop `consensus_bonus` back to 0 in `config.json` and the selector reverts to today's behaviour; `tie_breaker_order` is untouched.
4. **Bounded scope** — Best-of-N is already gated to `critical OR [best-of-n]` and `budget >= 5` (config `min_budget`), so this touches only the small fraction of pipelines that run N-candidate Build.

## Implementation Checklist (for `/harness:pipeline` run)

1. `orchestrator/parallel-dispatch-details.md` § Best-of-N Step 5 — specify the clustering computation (Jaccard ≥ 0.5 on changed files; identical pass/fail vectors on the union test set where a shared runner exists) and the "largest cluster wins, critic breaks intra-cluster ties" ordering.
2. `skills/best-of-n/config.json` — add `consensus_bonus: 60` to `selection_weights` above `subjective_quality_bonus`.
3. Selection implementation (the scorer behind `best-of-n/tests/test_best_of_n.sh`) — compute cluster sizes, apply `consensus_bonus`, populate `Cluster Sizes` in the output template.
4. `skills/best-of-n/tests/` — add cases: (a) two green candidates in one cluster vs one green outlier → cluster winner; (b) all candidates diverge (no cluster ≥ 2) → falls through to existing critic + objective tie-break; (c) one dominant green candidate → consensus is a no-op.
5. `scripts/test_best_of_n_skill_structure.sh` — update the canonical-template audit if the output sections change.
6. Open one observation on the next Best-of-N pipeline; record whether the consensus winner == the would-be critic winner, to build data on how often they diverge.

## Counter-arguments considered

- **"Two candidates can agree on the same *wrong* behaviour (shared misconception)."** True — which is why this never overrides tests/shape, only orders among candidates that already pass the AC tests and (where present) the spec-blind gate downstream. Consensus is a tie-break prior, not a correctness oracle.
- **"Clustering on Jaccard is crude."** It's the cheapest proxy and the one the harness already computes; behavioural (test-vector) clustering is the stronger signal and is included where a shared runner exists. Either is a strictly better cross-candidate decider than a judge score in the close regime.

## Rollback

Set `consensus_bonus: 0` in `config.json`; selection reverts to test-pass + shape + subjective + objective tie-break. `Cluster Sizes` returns to informational-only.

---

**Linked PR for the spec rewrite track:** this proposal. Dispatch `/harness:pipeline` with prompt: "Implement protocols/_proposals/2026-05-24-consensus-best-of-n-selection.md exactly as specified. Budget: 6. Critical: false."

# Proposal: Cascade-on-Failure — Cheap-First Dispatch, Escalate Only on Verification Failure

**Status:** PROPOSED (2026-05-28)
**Owner:** orchestrator-derived recommendation from external research (model cascading / routing — Augment, AI21 Maestro; Amp "Oracle" on-demand escalation; OpenHands verifier-gated selection)
**Implementation track:** requires `/pipeline` run (touches `orchestrator/parallel-dispatch-details.md`, `protocols/parallel-dispatch-protocol.md`, `skills/best-of-n/config.json` interaction, tests). Depends on `2026-05-28-orchestrator-flag-enforcement.md` landing first (needs `--model` to be applied).

---

## Problem

The harness escalates **by default**, not **on failure**. The expensive arms run regardless of whether the cheap arm would have sufficed:

- **Best-of-N** runs 2–3 candidates *up front* on a T6/budget≥7 slice — N parallel Opus builds before any one has been shown to be insufficient.
- **Advisor-mode** runs an Opus advisor *alongside* the Sonnet executor on every review (when enforced), paying both.
- Heavy-tier work pays its full dispatch shape even when a single Sonnet pass would have passed every gate.

External 2026 practice has converged on the opposite default — **cascade: start at the cheapest model that plausibly suffices, run the verification gates, and escalate to a stronger model / wider search ONLY when verification fails:**

- **Model cascading / routing** stops at the first model meeting a quality threshold; reported **up to ~94% cost reduction** in cascade configurations, **50–60% typical** for a 3-tier Haiku/Sonnet/Opus split (Augment routing guide; morphllm). The harness's own Explore subagent already defaults to Haiku — this generalises that instinct.
- **AI21 Maestro** (200k+ SWE-bench runs): orchestration / test-time compute is the lever, and frontier models with minimal tools now nearly match bespoke agents — i.e. *spend compute when needed, not by default*.
- **Amp's "Oracle"** calls a strong model **on demand** for the hard sub-problem in an isolated context, rather than running it for everything.
- **OpenHands** verifier-gated selection (critic Best@8 73.8% vs random 57.9%) shows the *verifier*, not up-front breadth, is what converts spend into correctness.

The harness already has the verification signal to gate a cascade — the ATDD/mutation/spec-blind gates **are** the escalation trigger. It just doesn't use them that way.

## Proposed Change

Make escalation **verification-triggered** rather than tier-triggered, for T4/T5 and as the *entry* arm of T6:

1. **Tier-1 attempt (cheap):** dispatch the Build slice with a **single Sonnet executor** (the harness default executor already), `effort=high`, no Best-of-N. Run the full gate stack (ATDD + mutation ≥70% + adversarial + DOM smoke + code-review).
2. **Escalate only on a gate failure that survives the in-cycle fix budget:** if the cheap attempt fails verification after its allotted in-cycle fix rounds, *then* escalate — first to **Opus single-candidate** (`--model opus`, the cheaper escalation), and only if that also fails, to **Best-of-N** (the widest, most expensive arm).
3. **Order the escalation ladder cheapest→widest:** `Sonnet single → Opus single → Best-of-N → PDR-RTV`. Each rung is entered only on the prior rung's verified failure. T6/`critical` may *start* one rung up (Opus single) but still only widens to BoN/PDR on failure.
4. **Reuse branch-on-retry** (`2026-05-28-branch-on-retry.md`): each escalation rung is seeded with the prior rung's failure summary, so the Opus attempt knows why the Sonnet attempt failed.
5. **Env hatch** `CLAUDE_CASCADE=off` reverts to today's tier-triggered up-front dispatch; `critical=true` work can be pinned to start at Opus via existing flags.

## Expected Saving

- **The headline cost lever for the common case.** Most well-specified T4/T5 slices pass on the first Sonnet attempt; today many of them still pay Opus (because effort/model enforcement is off — see the enforcement proposal) and some pay Best-of-N breadth they didn't need. Cascade pays the expensive arms only on the minority of slices that actually fail the cheap attempt — the regime where the spend is *justified by a verified failure*.
- Cascade configs report 50–94% cost reduction externally; the harness's realistic number is bounded by how often the cheap arm passes (high, for well-specified work) and depends on the enforcement proposal landing first.
- **It does not weaken correctness** — every rung runs the *same* full gate stack; cascade changes *when* compute is spent, not *whether* the output is verified.

## Why this is safe

1. **Verification floor is identical at every rung.** A cheap attempt only "passes" if it clears ATDD + mutation + spec-blind — the exact same gates a Best-of-N winner must clear. Cascade never ships less-verified code; it ships *the same verified code for less, when the cheap arm suffices.*
2. **Escalation is failure-gated, so quality is self-correcting** — if Sonnet can't do it, the gates fail and Opus/BoN take over automatically. The worst case is "we spent one cheap attempt before escalating," a small additive cost on the minority of slices that escalate.
3. **`critical`/T6 can start higher** — high-stakes work isn't forced to begin at Sonnet.
4. **Reversible** (`CLAUDE_CASCADE=off`) and **composes with** the existing Best-of-N gate, the fan-out cap (#154), and the quota governor (which can lower the cascade ceiling under quota pressure).

## Implementation Checklist (for `/pipeline` run)

1. **Land `2026-05-28-orchestrator-flag-enforcement.md` first** — cascade needs `--model` to actually switch executors between rungs.
2. `protocols/parallel-dispatch-protocol.md` + `orchestrator/parallel-dispatch-details.md` — define the escalation ladder (`Sonnet single → Opus single → Best-of-N → PDR-RTV`), the failure-gated transition (escalate only after in-cycle fix budget is exhausted on a gate failure), and the T6/`critical` start-rung rule.
3. `skills/best-of-n/config.json` interaction — BoN becomes a *cascade rung entered on failure*, not the T6 default entry; document that `min_budget`/tier gating still bounds whether BoN is reachable at all.
4. Seed each rung with the branch-on-retry failure summary.
5. `CLAUDE_CASCADE` env hatch + `critical` start-rung override.
6. `tests/` — (a) well-specified slice passes at Sonnet, no escalation, asserts no Opus/BoN spawn; (b) slice failing the cheap attempt escalates to Opus single, then BoN; (c) `critical=true` starts at Opus; (d) `CLAUDE_CASCADE=off` reverts to up-front dispatch.
7. Observation after 15 pipelines: % of slices that passed at the cheapest rung, and weekly token delta vs up-front dispatch.

## Counter-arguments considered

- **"Cheap-first adds a failed attempt's cost before escalating."** Only on the slices that escalate. For the majority that pass cheap, it's a large saving; for the minority that escalate, the prior-rung cost is small relative to the expensive arm — and branch-on-retry makes the escalated rung cheaper and more likely to succeed. Net positive unless the cheap arm almost never passes (which the gate-pass data will reveal).
- **"This is just Best-of-N with extra steps."** The opposite — BoN runs N candidates *concurrently and unconditionally*; cascade runs 1 and widens *only on a verified failure*. BoN spends to find the best of several plausible diffs; cascade spends only when the cheapest plausible diff is *proven* insufficient.
- **"Overlaps advisor-mode."** Advisor-mode is parallel post-hoc review (Opus advises on Sonnet's review). Cascade is sequential, failure-gated executor escalation in Build. They're orthogonal; cascade can run with advisor-mode off.

## Rollback

Set `CLAUDE_CASCADE=off`; dispatch reverts to tier-triggered up-front shape (#154 + Best-of-N gate unchanged). No state migration.

---

**Linked PR for the spec track:** this proposal. After the enforcement proposal lands, dispatch `/pipeline` with prompt: "Implement protocols/_proposals/2026-05-28-cascade-on-failure.md exactly as specified. Budget: 7. Critical: true."

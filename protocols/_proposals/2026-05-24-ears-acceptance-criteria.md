# Proposal: EARS-Notation Acceptance Criteria to Sharpen Auto-Derived Test Oracles

**Status:** IMPLEMENTED (ws-g-spec-grounding) — item 4 (ac_forms on spec-blind output) deferred to follow-on pipeline
**Owner:** orchestrator-derived recommendation from external research (GitHub Spec Kit, AWS Kiro, agent-test-oracle literature)
**Implementation track:** requires `/harness:pipeline` run (touches `skills/story-writing`, light touch to `skills/spec-blind-validate` input contract)

---

## Problem

The harness's strongest production-readiness asset is `spec-blind-validate`: a Final-Gate teammate that authors black-box tests **from the AC plan + public surface only, never from `src/` or the diff**, enforced by three PreToolUse guards. This is exactly the independent-oracle-provenance remedy the fresh literature prescribes (arXiv 2602.07900, Feb 2026: agent-written tests about an agent's *own* code "fundamentally cannot verify functional correctness against the intended specification"; arXiv 2601.05542 on oracle generation). **This gate should not change — it is best-in-class.**

The gate's ceiling, though, is set by the **quality of its only trustworthy input: the ACs in `plan.md`.** If an AC is prose like *"the endpoint should handle errors gracefully,"* the spec-blind validator must guess the observable contract — and a guessed oracle is a weak oracle. The mainstream 2026 spec-driven tools converged on a fix:

- **AWS Kiro** enforces **EARS notation** for requirements — *"WHEN <trigger> the system SHALL <response>"* — before any code, behind a human approval gate.
- **GitHub Spec Kit** (~71K stars) splits Specify → Plan → Tasks on the same machine-checkable-spec premise.

EARS turns each AC into a single trigger→response clause with explicit pre-conditions, which is **directly mechanically translatable into a behavioural test** — removing the guesswork between "the AC" and "the oracle."

## Proposed Change

1. **Add an EARS-shaped AC template to `skills/story-writing`.** Each AC is authored as one of the five EARS forms:
   - Ubiquitous: *"The system SHALL <response>."*
   - Event: *"WHEN <trigger> the system SHALL <response>."*
   - State: *"WHILE <state> the system SHALL <response>."*
   - Unwanted: *"IF <condition> THEN the system SHALL <response>."*
   - Optional: *"WHERE <feature> the system SHALL <response>."*
2. **Make EARS advisory-then-default, not mandatory day one.** Story-writing emits ACs in EARS where the requirement fits a trigger→response shape; free-form is still permitted for genuinely narrative ACs, flagged so spec-blind knows it's deriving an oracle from prose.
3. **No change to `spec-blind-validate`'s read model** — it keeps reading `plan.md` ACs verbatim. It simply receives sharper input; an EARS clause yields a near-mechanical test (trigger → invoke → assert response), a prose AC keeps today's best-effort derivation.
4. **Record AC form in the verdict payload** so we can later correlate "EARS AC" vs "prose AC" against spec-blind pass-rate and `SPEC_BLIND_FAILED` incidence — turning the rollout into measured evidence rather than faith.

## Expected Effect

- **Fewer "looks-right, isn't-right" escapes.** Sharper oracles mean spec-blind catches more cases where the build's own tests codify the same misconception as the code (the SWE-Bench-Pro-vs-Verified failure mode the skill already targets).
- **Less oracle guesswork** → fewer spurious `SPEC_BLIND_FAILED` from ambiguous ACs, and fewer false-passes from under-specified ones.
- Tighter Plan→Build handoff generally: EARS ACs are unambiguous enough that the architect's failing-test stubs (`plan.md` per-AC stubs) become more deterministic.

## Why this is safe

1. **Purely additive to the input contract.** No gate logic, no provenance change, no new spawn. The strongest existing safeguard (`spec-blind-validate`) is untouched.
2. **Backward-compatible** — prose ACs still validate; EARS is preferred where it fits, not forced.
3. **Measured** — the AC-form field lets us prove or disprove the benefit on real pipelines before making EARS mandatory (or reverting).
4. **Mainstream, not experimental** — EARS is a 2009 requirements-engineering standard adopted by Kiro and widely used; this is borrowing a proven notation, not a research bet.

## Implementation Checklist (for `/harness:pipeline` run)

1. `skills/story-writing/SKILL.md` — add an § Acceptance Criteria Form section documenting the five EARS templates with one worked example each; instruct: prefer EARS where the AC is a trigger→response, fall back to prose only for narrative ACs.
2. `skills/story-writing` output — tag each AC with `form: ears-<type> | prose` in the `plan.md` AC list.
3. `skills/spec-blind-validate/SKILL.md` § Inputs — note that ACs may carry a `form` tag; an EARS clause maps trigger→arrange, response→assert; no read-model change.
4. Verdict payload — add `ac_forms: {ears: N, prose: M}` to the spec-blind output so `/harness:learn` can correlate form vs pass-rate.
5. Tests — `skills/story-writing/tests/` assert each EARS form renders correctly and the `form` tag is emitted; one `spec-blind-validate` fixture with an EARS AC asserting the derived test shape.
6. Open an observation after 10 pipelines comparing `SPEC_BLIND_FAILED` rate and false-pass incidence on EARS vs prose ACs; if EARS shows no benefit, revert to prose-default.

## Counter-arguments considered

- **"EARS is rigid; some requirements don't fit."** Hence advisory-then-default with a prose escape hatch — narrative ACs are still allowed and flagged.
- **"This adds story-writing overhead."** Minimal — EARS is a sentence template, and the downstream payoff (sharper oracles, more deterministic test stubs) compounds across Build, Final Gate, and Review.
- **"Why not just improve the spec-blind validator's guessing?"** Because the literature is clear the leverage is in *input spec quality and oracle independence*, not a smarter guesser — and the validator is already independent. Sharper ACs raise its ceiling without touching its (correct) design.

## Rollback

Remove the EARS § from story-writing and the `form` tag; ACs revert to free-form prose. `spec-blind-validate` is unaffected either way.

---

**Linked PR for the spec rewrite track:** this proposal. Dispatch `/harness:pipeline` with prompt: "Implement protocols/_proposals/2026-05-24-ears-acceptance-criteria.md exactly as specified. Budget: 5. Critical: false."

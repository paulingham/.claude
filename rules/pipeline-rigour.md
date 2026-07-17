# Pipeline Rigour Invariants

These laws apply in BUILD and PIPELINE gears only. In PAIR mode only `rules/safety.md` is in force. Laws are globally numbered 1-8 across safety.md + pipeline-rigour.md; this file carries a non-contiguous subset.

## Iron Laws (rigour subset: 1, 5, 7)

These are absolutes. No exceptions. No "just this once."

1. [ASPIRATIONAL] **NO ACCEPTANCE CRITERION SHIPS WITHOUT (a) a failing-then-passing test for that AC in the diff and (b) mutation score ≥ 70% on changed lines.** (Full ATDD cycle: `protocols/atdd-procedure.md`.)
5. [ASPIRATIONAL] **NO PHASE SKIPPED. NO GATE BYPASSED. NO SKILL OMITTED.** Every pipeline phase runs the corresponding skill; verdicts gate advancement. (Detail: `protocols/pipeline-protocol.md`.)
7. [ASPIRATIONAL] **EVERY PIPELINE PRODUCES AN OBSERVATION.** No exceptions — successes and failures both. The continuous learning loop depends on data volume. (Format and pipeline: `protocols/reflection-protocol.md` § Capture Pipeline Observation, `protocols/autonomous-intelligence.md` § Observation Capture.)

## Pipeline Phase Order

`Plan → Plan Validation → Build (incl. code-review as final step) → Security Review → Final Gate (Verify + Test + Accept + Patch Critique) → Ship → Deploy → Reflect`. No phase skipped. Every phase has a corresponding skill. Code-review is no longer its own phase — it runs as the final step of Build (the value-add is "second model with different priors", not a separate phase boundary). Security review remains a separate phase (orthogonal concern). Reflect always runs (§ Iron Law 7). Build has three dispatch variants — standard, Best-of-N, and PDR-RTV — selected by `/harness:intake` flags with precedence `pdr_rtv > bestofn > standard`. Detail: `protocols/pipeline-protocol.md`.

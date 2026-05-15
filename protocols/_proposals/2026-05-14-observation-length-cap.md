# Proposal: Observation-length Cap (PostToolUse Hook)

**Status:** advisory at v2.1.140 (log-only)
**Date:** 2026-05-14
**Companion slice:** `model-demotion-pass-2026-05` slice A (this proposal) → slice D (hook + settings.json wiring)

## Summary

Session-memory observation files (`session-memory/*/build-test.md`, `patterns.md`, `fragility.md`) grow unbounded today. Recon flagged the lack of per-write length signal as a fragility but had no measurement basis for a concrete cap. This proposal introduces an advisory PostToolUse hook on `Edit` that estimates token count per write and logs `would_truncate` when the estimate exceeds a soft cap. No truncation happens at v2.1.140 — the hook is forensic only, and the data drives the enforcement-flip decision.

## 250-token cap rationale

The 250-token cap (≈1000 chars via the canonical `chars/4` estimate used in `hooks/_lib/tool-output-bytes-emit.py:45`) is chosen as a deliberately tight initial target:

- A 250-token observation fits comfortably inside one model "thought" without dominating context budget when N observations are spliced into a Build spawn (typical N = 3-5).
- Tight initial caps surface real over-runs in the log immediately rather than burying them behind a generous threshold. If ≥20% of writes trip the cap, that's a signal we picked the wrong number — not a signal observations are inherently large.
- The recompute trigger (below) explicitly allows retuning to 400 tokens if 250 proves too tight in practice. We bias toward measuring first.

## Event definition

`event := one JSONL line` written by the hook to `metrics/{session-id}/observation-length.jsonl`. Each event captures one `Edit` operation against a watched session-memory path. Schema:

```json
{
  "ts": "<iso8601>",
  "agent_role": "<role>",
  "file_path": "<absolute path>",
  "char_count": <int>,
  "estimated_tokens": <int>,
  "would_truncate": <bool>,
  "cap_tokens": 250
}
```

`would_truncate` is `true` iff `estimated_tokens > cap_tokens`. No truncation actually happens at v2.1.140 — the flag names the counterfactual under enforcement.

## Recompute trigger

`event := one JSONL line; recompute trigger = rolling window of last 50 events with >10 (>20%) would_truncate=true → retune to 400`.

In prose: every Reflect step counts the trailing 50 events in `observation-length.jsonl`. If more than 10 of them (>20%) have `would_truncate=true`, the cap is retuned upward to 400 tokens before any enforcement flip is considered. This prevents the cap from being a hostile choke point if observation length is genuinely larger than the initial estimate predicted.

## Concrete flip trigger

**Flip trigger:** flip from `status: advisory` to `status: enforced` once **50 events** have been recorded AND fewer than 20% of them carry `would_truncate=true` over the rolling window of 50. If the ratio is ≥20%, retune the cap to 400 first and re-measure — do not flip until the new cap shows <20% truncation rate.

The 50-events / <20% bar is meant to be cheap to reach (50 events ≈ a handful of multi-slice pipelines) but disciplined enough to require real-data justification before enforcement.

## Named follow-up: resolve_model_conditional bash-wrapper integration

`resolve_model_conditional()` lands in `hooks/_lib/advisor_resolver.py` in slice B2 as a pure Python function. **Not in this PR:** the bash wrapper (`pre-agent-advisor.sh` or a peer hook) that would call the resolver per-spawn and emit a structured log line akin to the existing `metrics/{session}/advisor-dispatch.jsonl` format. Wiring the resolver into spawn dispatch is the same advisory-at-v2.1.140 posture as the existing `pre-agent-advisor.sh` and is deliberately deferred to a follow-up PR so this pass stays within the slice plan.

Follow-up tracking lives in this proposal until the wrapper PR is opened; at that point, this section becomes a back-pointer.

## planning-agent canary (slice C AC-C5)

The planning-agent role demotes from Sonnet to Haiku in slice C. Because planning-agent emits advisory verdicts (`PLAN_REFINED` / `PLAN_UNCHANGED`) and never gates Build completion, a silent quality regression on Haiku would not surface as a pipeline failure — it would surface as a slow drift toward zero refinements.

**Canary:** Monitor PLAN_REFINED count over next 3 multi-slice pipelines; revert if zero refinements.

`/health-scan` step counts the `PLAN_REFINED` vs `PLAN_UNCHANGED` ratio over the rolling 3 most recent multi-slice pipelines. If the ratio is zero (zero refinements emitted across 3 pipelines), the demotion is presumed to have degraded the role and slice C is reverted via a single-commit revert. This is the operator-quality signal called out as MED-8 in the round-2 plan.

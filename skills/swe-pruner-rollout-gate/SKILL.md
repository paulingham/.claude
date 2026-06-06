---
name: swe-pruner-rollout-gate
description: Data-gated rollout gate for SWE-Pruner advisory context filter. Evaluates JSONL telemetry to determine if the pruner is ready to flip from advisory to enforcing mode.
status: DEFERRED
verdicts:
  - ROLLOUT_GATE_PASS
  - ROLLOUT_GATE_FAIL
  - INSUFFICIENT_DATA
---

# SWE-Pruner Rollout Gate — STUB (DEFERRED)

## Status

**DEFERRED.** This skill is a stub. The enforcing flip requires data
from >= 50 pipeline runs spanning >= 14 days. Invoke this skill only
after that threshold is reached.

## Review Cadence

After >= 50 pipelines AND >= 14 days since merge, invoke
`/harness:swe-pruner-rollout-gate` to evaluate whether the pruner
is ready to flip from advisory to enforcing mode.

## Verdicts

- **ROLLOUT_GATE_PASS**: All criteria met; operator may author flip PR.
- **ROLLOUT_GATE_FAIL**: Criteria not met (regression or thresholds missed).
- **INSUFFICIENT_DATA**: Fewer than 50 pipelines or fewer than 14 days of data.

## Promotion Criteria (ROLLOUT_GATE_PASS requires ALL)

1. `token_delta_p50 >= 5%` — median token savings per spawn >= 5%
2. `n_pipelines >= 50` — at least 50 pipeline runs observed
3. `days_since_merge >= 14` — at least 14 calendar days of soak
4. `eval_regression_count == 0` — no eval regressions vs baseline
5. Operator manual review of per-session JSONL

## Flip Surface

Replace the `exit 0` in the advisory branch of `pre-agent-swe-pruner.sh`
with the enforcing path after ROLLOUT_GATE_PASS. This is a pure-deny flip
(one-line change). No `modified_tool_input` schema required.

## Telemetry Source

JSONL records at `${CLAUDE_PLUGIN_DATA}/metrics/{session}/swe-pruner.jsonl`.
Aggregate across sessions to compute p50 token_delta and n_pipelines.

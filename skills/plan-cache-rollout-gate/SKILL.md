---
name: "plan-cache-rollout-gate"
description: "Executable rollout gate that decides whether the agentic plan-cache is ready to flip from shadow-mode to on-mode. Aggregates `metrics/*/plan-cache.jsonl` across the larger of the last 30 pipelines or the last 14 days, scores three thresholds, and returns ROLLOUT_GATE_PASS / ROLLOUT_GATE_FAIL / INSUFFICIENT_DATA. Invoke this skill before authoring the flip-to-on PR; PASS payload is the merge evidence (HIGH-prod-1)."
verdict: "ROLLOUT_GATE_PASS"
phase: "utility"
dispatch: "skill-tool"
argument-hint: "Optional: --metrics-dir <path> (default $CLAUDE_HOOK_LOG_DIR or $CLAUDE_PLUGIN_DATA/metrics or $CLAUDE_CONFIG_DIR/metrics or ~/.claude/metrics)"
---

# Plan Cache Rollout Gate

## What This Skill Does

Reads every `plan-cache.jsonl` line emitted by `hooks/plan-cache-audit.sh`
since the rollout started, computes three thresholds against the cached-plan
adapter's empirical performance, and emits a structured verdict. The verdict
binds the future flip-to-`on` PR (the only PR that turns HIT-serving on for
real users): that PR cannot merge without an attached `ROLLOUT_GATE_PASS`
payload from this skill (plan.md § Decision Drivers — HIGH-prod-1, MEDIUM-prod-2).

## When to Invoke

- **Operator request**: "is the plan-cache ready to flip on?" / "show me
  the cache hit-rate this month" / "run the rollout gate".
- **Before authoring** the `CLAUDE_PLAN_CACHE_MODE=on` PR. The PR description
  MUST include the PASS payload.
- **Do NOT use when**: a single pipeline's cache behaviour is the question —
  that lives in `pipeline-state/{task-id}/scratchpad/` and in the per-pipeline
  `plan-cache.jsonl` line.

## Inputs

- **Filesystem**:
  `$CLAUDE_HOOK_LOG_DIR/<session>/plan-cache.jsonl` (default
  `${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-~/.claude}}/metrics/<session>/plan-cache.jsonl`).
  One file per pipeline session. Each line has the 10 keys emitted by
  `hooks/_lib/plan-cache-audit-emit.py`:
  `task_id, cache_key, verdict, adapter_cost_tokens, miss_reason,
  hit_template_path, hit_count_after, pv_outcome, session_id, timestamp,
  saved_architect_tokens_estimate`.
- **Environment**: `CLAUDE_HOOK_LOG_DIR` overrides metrics root (highest priority);
  `CLAUDE_PLUGIN_DATA` beats `CLAUDE_CONFIG_DIR` beats `$HOME/.claude`.

## Procedure

The skill is a one-shot script wrapper around the aggregator.

### Step 1 — Run the aggregator

```bash
python3 hooks/_lib/plan-cache-rollout-gate.py \
  --metrics-dir "${CLAUDE_HOOK_LOG_DIR:-${CLAUDE_PLUGIN_DATA:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}/metrics}"
```

Stdout is a JSON document; capture and parse it.

### Step 2 — Decide

- `verdict: ROLLOUT_GATE_PASS` — all three thresholds met. Author the
  flip-to-`on` PR and paste the payload into the PR description as evidence.
- `verdict: ROLLOUT_GATE_FAIL` — at least one threshold failed; the
  payload `failed_thresholds[]` cites which (`hit_rate < 0.10`,
  `pv_pass_rate_on_hit < 0.95`, or `cost_delta <= 0`). Do NOT author the
  flip PR; investigate the failing dimension first.
- `verdict: INSUFFICIENT_DATA` — fewer than 30 distinct pipelines AND less
  than 14 days of records. Continue running in shadow-mode; re-invoke the
  gate after more data arrives.

## Thresholds (verbatim)

These values are the merge contract for the flip-to-`on` PR. Changing them
is a plan-level decision, NOT a tuning knob.

| Metric | Threshold |
|---|---|
| `hit_rate` | `>= 0.10` |
| `pv_pass_rate_on_hit` | `>= 0.95` |
| `cost_delta` | `> 0` |

Where:

- `hit_rate = hits / (hits + misses_excluding_shadow_mode_reason)` — the
  denominator deliberately excludes `miss_reason=shadow-mode` records (those
  are by-design misses during the rollout window, not real cache failures).
- `pv_pass_rate_on_hit = (HIT lines with pv_outcome == PLAN_APPROVED) / total HIT count` — proxies the paper's 96.6% optimal-quality figure.
- `cost_delta = sum(saved_architect_tokens_estimate) - sum(adapter_cost_tokens)` — net token savings across HIT lines. `saved_architect_tokens_estimate` is set to a constant
  `SAVED_TOKENS_PER_HIT = 10000` on HIT records by
  `hooks/_lib/plan-cache-audit-emit.py` (conservative under-estimate of the
  recon + architect spawn cost we skip on HIT path — refine after first
  measurement window).

## Window Selection

Use the LARGER of:
- **Last N=30 pipelines** (distinct `session_id`s), or
- **Last 14 days** of records (rolling window).

INSUFFICIENT_DATA fires only when BOTH `sessions_seen < 30` AND
`days_span < 14`. This protects against premature flips on a quiet week and
against ancient stale records on a slow-rollout month.

## Output

JSON document on stdout. Schema:

```json
{
  "verdict": "ROLLOUT_GATE_PASS | ROLLOUT_GATE_FAIL | INSUFFICIENT_DATA",
  "sessions_seen": <int>,
  "days_span": <float>,
  "thresholds": {
    "hit_rate_min": 0.10,
    "pv_pass_rate_min": 0.95,
    "cost_delta_min_strict": 0
  },
  "metrics": {
    "hits": <int>,
    "real_misses": <int>,
    "hit_rate": <float>,
    "pv_pass_rate_on_hit": <float>,
    "cost_delta": <int>
  },
  "failed_thresholds": ["hit_rate=0.05 < 0.10", ...]
}
```

INSUFFICIENT_DATA payloads omit `metrics`, `thresholds`, and
`failed_thresholds` and include a `floor` block instead.

## Verdict

| Verdict | Meaning | Downstream |
|---|---|---|
| `ROLLOUT_GATE_PASS` | All three thresholds met. | Operator authors flip-to-`on` PR with payload as evidence. |
| `ROLLOUT_GATE_FAIL` | One or more thresholds failed. | Operator investigates failed dimension; flip PR is blocked. |
| `INSUFFICIENT_DATA` | <30 pipelines AND <14 days. | Continue shadow-mode; re-run later. |

## Anti-Patterns

- **Lowering a threshold without a plan-amendment**: the three numbers
  (0.10, 0.95, 0) come from the paper + decision drivers; mutating them in
  this skill body is a contract change that requires updating plan.md
  and the verdict-catalog row.
- **Counting shadow-mode misses against `hit_rate`**: shadow-mode is the
  default mode during rollout; treating its misses as cache failures would
  pin `hit_rate` near zero and block the flip indefinitely.
- **Bypassing the gate**: the flip-to-`on` PR is the load-bearing rollout
  event; its merge is gated on a PASS payload, not on operator judgement.

## Tests

`tests/skills/test_plan_cache_rollout_gate.bats` exercises ACs G1..G7 against
the Python aggregator with hermetic metrics fixtures.
`tests/rules/test_verdict_catalog.bats` § G8 asserts the three catalog rows.

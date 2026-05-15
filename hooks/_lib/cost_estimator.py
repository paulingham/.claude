"""Token-to-USD cost estimator for Claude Code tool-timings records.

Sums per-call cost from `tool-timings.jsonl`-shaped records. Used by the
`/cost-report` skill (and B12.2's per-pipeline observation enrichment) to
attach a dollar figure to pipeline activity.

Pricing source-of-truth (per-million tokens, USD), as published by Anthropic
on the model pricing pages (claude-opus-4-5-20251101 GA 2025-11-24). Rates
verified against https://www.anthropic.com/pricing on 2026-05-15. To update:
edit the PRICING_PER_MILLION dict at module top, run the test suite, ship.

| Model                           | Input $/M | Output $/M | Cache-read $/M |
|---------------------------------|-----------|------------|----------------|
| claude-opus-4-5-20251101        | 5.00      | 25.00      | 0.50           |
| claude-sonnet-4-6               | 3.00      | 15.00      | 0.30           |
| claude-haiku-4-5-20251001       | 0.80      | 4.00       | 0.08           |

Legacy ``claude-opus-4-7`` key retained for a 7-day dual-accept window
(DEPRECATED-REMOVE-AFTER-2026-05-22) so the ``/cost-report`` aggregator can
sum records emitted before the rate_version flip.

Cache-read tokens are billed at 0.10x the input rate (Anthropic prompt-cache
convention). Cache-creation tokens are billed at the regular input rate.

Public API:
- `estimate_cost_usd(timings: list[dict]) -> float`
- `estimate_cost_usd_per_pipeline(timings_path: str) -> dict[str, float]`

Pure stdlib only — no third-party deps. Unknown models contribute 0.0 to the
sum (graceful fallback) and emit a one-line stderr warning per unique unknown
model id (deduplicated to avoid log spam).
"""
import json
import sys
from typing import Iterable

# Pricing in USD per 1,000,000 tokens. Single source of truth — DRY.
# Cache-read rate is 0.10 * input rate per Anthropic's prompt-cache pricing.
PRICING_PER_MILLION = {
    "claude-opus-4-5-20251101": {
        "input": 5.00, "output": 25.00, "cache_read": 0.50,
    },
    # DEPRECATED-REMOVE-AFTER-2026-05-22 — dual-accept window for rate_version
    # rollback. Aggregator must still sum opus-4-7 records emitted before the
    # opus-4-5-2026-05 flip. Drop this key after the 7-day window expires.
    "claude-opus-4-7": {
        "input": 5.00, "output": 25.00, "cache_read": 0.50,
    },
    "claude-sonnet-4-6": {
        "input": 3.00, "output": 15.00, "cache_read": 0.30,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80, "output": 4.00, "cache_read": 0.08,
    },
}

_PER_MILLION = 1_000_000.0
_warned_models: set[str] = set()


def _warn_unknown_model_once(model: str) -> None:
    if model in _warned_models:
        return
    _warned_models.add(model)
    sys.stderr.write(
        f"cost_estimator: unknown model {model!r} — billed at $0.00 "
        "(update PRICING_PER_MILLION to track)\n"
    )


def _record_cost_usd(record: dict) -> float:
    """Compute USD cost for a single tool-timings record.

    Unknown models return 0.0 (graceful fallback). Missing token fields
    default to 0 — partial records are tolerated.
    """
    model = record.get("model", "")
    rates = PRICING_PER_MILLION.get(model)
    if rates is None:
        if model:
            _warn_unknown_model_once(model)
        return 0.0
    input_tokens = record.get("input_tokens", 0) or 0
    output_tokens = record.get("output_tokens", 0) or 0
    cache_read = record.get("cache_read_input_tokens", 0) or 0
    cache_create = record.get("cache_creation_input_tokens", 0) or 0
    # cache-creation tokens bill at regular input rate (write-through cache).
    billable_input = input_tokens + cache_create
    return (
        billable_input * rates["input"]
        + output_tokens * rates["output"]
        + cache_read * rates["cache_read"]
    ) / _PER_MILLION


def estimate_cost_usd(timings: Iterable[dict]) -> float:
    """Sum USD cost across a sequence of tool-timings records."""
    return sum(_record_cost_usd(r) for r in timings)


def _read_jsonl(path: str) -> list[dict]:
    """Read a JSONL file into a list of dicts. Tolerates malformed lines."""
    records: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    return records


def estimate_cost_usd_per_pipeline(timings_path: str) -> dict[str, float]:
    """Read a tool-timings JSONL file and group total USD cost by `task_id`.

    Records lacking a `task_id` are skipped (cannot be attributed to a pipeline).
    Missing input file returns an empty dict, not an exception.
    """
    by_task: dict[str, float] = {}
    for record in _read_jsonl(timings_path):
        task_id = record.get("task_id")
        if not task_id:
            continue
        by_task[task_id] = by_task.get(task_id, 0.0) + _record_cost_usd(record)
    return by_task

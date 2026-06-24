"""Token-to-USD cost estimator for Claude Code tool-timings records.

Sums per-call cost from `tool-timings.jsonl`-shaped records. Used by the
`/cost-report` skill (and B12.2's per-pipeline observation enrichment) to
attach a dollar figure to pipeline activity.

Pricing source-of-truth (per-million tokens, USD), as published by Anthropic
on the model pricing pages (claude-opus-4-8 GA 2026-06). Rates verified
against https://www.anthropic.com/pricing on 2026-06-22. To update: edit the
PRICING_PER_MILLION dict at module top, run the test suite, ship.

| Model                           | Input $/M | Output $/M | Cache-read $/M |
|---------------------------------|-----------|------------|----------------|
| claude-opus-4-7                 | 5.00      | 25.00      | 0.50           |
| claude-opus-4-8                 | 5.00      | 25.00      | 0.50           |
| claude-sonnet-4-6               | 3.00      | 15.00      | 0.30           |
| claude-haiku-4-5-20251001       | 0.80      | 4.00       | 0.08           |

Cache-read tokens are billed at 0.10x the input rate (Anthropic prompt-cache
convention). Cache-creation tokens are billed at the regular input rate.

Public API:
- `estimate_cost_usd(timings: list[dict]) -> float`
- `estimate_cost_usd_per_pipeline(timings_path: str) -> dict[str, float]`

Pure stdlib only — no third-party deps. Unknown models contribute 0.0 to the
sum (graceful fallback) and emit a one-line stderr warning per unique unknown
model id (deduplicated to avoid log spam).
"""
# WHY: PEP-604 union annotations (X | None) are runtime-evaluated under Python 3.9
# and crash at import with TypeError. This import defers annotation evaluation
# (PEP-563), matching the ~40 other _lib files that use the same pattern.
from __future__ import annotations

import json
import sys
from typing import Iterable

# Pricing in USD per 1,000,000 tokens. Single source of truth — DRY.
# Cache-read rate is 0.10 * input rate per Anthropic's prompt-cache pricing.
PRICING_PER_MILLION = {
    "claude-opus-4-7": {
        "input": 5.00, "output": 25.00, "cache_read": 0.50,
    },
    "claude-opus-4-8": {
        "input": 5.00, "output": 25.00, "cache_read": 0.50,
    },
    "claude-sonnet-4-6": {
        "input": 3.00, "output": 15.00, "cache_read": 0.30,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80, "output": 4.00, "cache_read": 0.08,
    },
}

# WHY: GA point-bumps (claude-opus-4-9, ...) must not silently bill $0.
# Maps a known family stem to the exact PRICING_PER_MILLION key for that
# family's base price — a pointer, never a duplicated literal.
_FAMILY_PREFIX_PRICE = {
    "claude-opus-":   "claude-opus-4-8",
    "claude-sonnet-": "claude-sonnet-4-6",
    "claude-haiku-":  "claude-haiku-4-5-20251001",
}

_PER_MILLION = 1_000_000.0
_warned_models: set[str] = set()

# WHY: Claude Code writes synthetic assistant turns with model == "<synthetic>".
# This is a compaction/injected-content sentinel — not a real model, carries no
# billable usage. Exclude from pricing lookup and unknown-model warnings entirely.
_NON_BILLABLE_MODELS: frozenset = frozenset({"<synthetic>"})


def _warn_unknown_model_once(model: str) -> None:
    if model in _warned_models:
        return
    _warned_models.add(model)
    msg = f"cost_estimator: unknown model {model!r} — billed at $0.00 (update PRICING_PER_MILLION to track)\n"
    sys.stderr.write(msg)


def _resolve_pricing_key(model: str) -> str | None:
    # WHY: exact hit wins; prefix path never shadows a known exact key.
    if model in PRICING_PER_MILLION:
        return model
    matched = next((base for stem, base in _FAMILY_PREFIX_PRICE.items() if model.startswith(stem)), None)
    return matched


def _token_cost_usd(rates: dict, record: dict) -> float:
    # WHY: cache-creation tokens bill at input rate (write-through cache pricing).
    inp = (record.get("input_tokens", 0) or 0) + (record.get("cache_creation_input_tokens", 0) or 0)
    out = record.get("output_tokens", 0) or 0
    cread = record.get("cache_read_input_tokens", 0) or 0
    return (inp * rates["input"] + out * rates["output"] + cread * rates["cache_read"]) / _PER_MILLION


def _record_cost_usd(record: dict) -> float:
    model = record.get("model", "")
    if model in _NON_BILLABLE_MODELS:
        return 0.0
    rates = PRICING_PER_MILLION.get(_resolve_pricing_key(model) or "")
    if rates is None:
        if model:
            _warn_unknown_model_once(model)
        return 0.0
    return _token_cost_usd(rates, record)


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


# WHY: sentinel distinguishes "no tagged records found" from a genuine $0.00 run.
# eval_run_id tagging requires BOTH EVAL_RUN_ID and EVAL_CASE_ID to be set at
# cost-tracker.sh emit time; absent tagging → USD unavailable, not $0.
USD_UNAVAILABLE_SENTINEL = object()


def _usage_by_model_cost(record: dict) -> float:
    # WHY: unrolls usage_by_model into flat records for _record_cost_usd (SSOT).
    return sum(_record_cost_usd({**u, "model": m})
               for m, u in record.get("usage_by_model", {}).items())
def _run_records(run_id: str, costs_path: str):
    return (r for r in _read_jsonl(costs_path) if r.get("eval_run_id") == run_id)
def estimate_cost_usd_for_run(run_id: str, costs_path: str) -> object:
    # WHY: filters costs.jsonl by eval_run_id; returns sentinel not $0 when absent.
    records = list(_run_records(run_id, costs_path))
    if not records:
        return USD_UNAVAILABLE_SENTINEL
    return sum(_usage_by_model_cost(r) for r in records)


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

"""Cost JSONL parser."""
from __future__ import annotations

from pathlib import Path

from jsonl_io import iter_jsonl
from models import CostRecord
from tiering import normalise_tier

REQUIRED = ("pipeline_id", "agent_role", "model", "total_cost_usd")


def _parse_cost(rec: dict) -> CostRecord | None:
    if not all(k in rec for k in REQUIRED):
        return None
    tier = normalise_tier(str(rec["model"]))
    if tier is None:
        return None
    try:
        cost = float(rec["total_cost_usd"])
    except (TypeError, ValueError):
        return None
    return CostRecord(str(rec["pipeline_id"]), str(rec["agent_role"]), tier, cost)


def read_costs(path: Path) -> list[CostRecord]:
    out: list[CostRecord] = []
    for _i, rec in iter_jsonl(path):
        cr = _parse_cost(rec)
        if cr is not None:
            out.append(cr)
    return out

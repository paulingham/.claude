"""Build per-(role, classification, tier) subcells from costs+observations."""
from __future__ import annotations

import sys
from typing import Iterable

from models import CostRecord, Observation, Subcell


def build_subcells(costs: Iterable[CostRecord], obs_by_pid: dict[str, Observation]) -> dict[tuple, Subcell]:
    cells: dict[tuple, Subcell] = {}
    for cr in costs:
        obs = obs_by_pid.get(cr.pipeline_id)
        if obs is None:
            print(f"WARN: cost pipeline_id {cr.pipeline_id} has no observation", file=sys.stderr)
            continue
        key = (cr.agent_role, obs.classification, cr.model_tier)
        sc = cells.setdefault(key, Subcell(cr.agent_role, obs.classification, cr.model_tier))
        sc.obs.append(obs)
        sc.total_cost += cr.total_cost_usd
    return cells


def group_cells(subcells: dict[tuple, Subcell]) -> dict[tuple[str, str], list[Subcell]]:
    grouped: dict[tuple[str, str], list[Subcell]] = {}
    for (role, classification, _tier), sc in subcells.items():
        grouped.setdefault((role, classification), []).append(sc)
    return grouped

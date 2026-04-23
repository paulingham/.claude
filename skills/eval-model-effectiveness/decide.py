"""Per-cell downgrade/upgrade/no-change decision logic."""
from __future__ import annotations

from constants import LOCKED_ROLES, MIN_OBS
from downgrade import find_downgrade
from models import CellDecision, Subcell
from upgrade import find_upgrade


def _decide_change(role: str, cls: str, qualified: list[Subcell], allsc: list[Subcell]) -> CellDecision:
    dg = find_downgrade(qualified)
    max_n = max(s.n for s in qualified)
    if dg is not None:
        return CellDecision(role, cls, "DOWNGRADE", dg[0], dg[1], max_n, allsc)
    up = find_upgrade(qualified)
    if up is not None:
        return CellDecision(role, cls, "UPGRADE", up[0], up[1], max_n, allsc)
    return CellDecision(role, cls, "NO CHANGE", max_n=max_n, subcells=allsc)


def decide(role: str, classification: str, subcells: list[Subcell]) -> CellDecision:
    if role in LOCKED_ROLES:
        return CellDecision(role, classification, "LOCKED", subcells=subcells)
    qualified = [s for s in subcells if s.n >= MIN_OBS]
    if not qualified:
        max_n = max((s.n for s in subcells), default=0)
        return CellDecision(role, classification, "INSUFFICIENT_DATA", max_n=max_n, subcells=subcells)
    return _decide_change(role, classification, qualified, subcells)

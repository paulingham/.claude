"""Downgrade candidate detection."""
from __future__ import annotations

from constants import COST_RATIO, SUCCESS_TOLERANCE, TIERS
from metrics import cost_per_success, success_rate
from models import Subcell


def _is_downgrade(cheap: Subcell, exp: Subcell) -> bool:
    if success_rate(cheap) < success_rate(exp) - SUCCESS_TOLERANCE:
        return False
    return cost_per_success(cheap) < COST_RATIO * cost_per_success(exp)


def find_downgrade(qualified: list[Subcell]) -> tuple[str, str] | None:
    by_tier = {s.tier: s for s in qualified}
    for exp_tier in reversed(TIERS):
        exp = by_tier.get(exp_tier)
        if exp is None:
            continue
        for cheap_tier in TIERS[: TIERS.index(exp_tier)]:
            cheap = by_tier.get(cheap_tier)
            if cheap is not None and _is_downgrade(cheap, exp):
                return (exp_tier, cheap_tier)
    return None

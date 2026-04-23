"""Upgrade candidate detection."""
from __future__ import annotations

from constants import TIERS, UPGRADE_MIN_OBS, UPGRADE_SUCCESS_THRESHOLD
from metrics import success_rate
from models import Subcell


def find_upgrade(qualified: list[Subcell]) -> tuple[str, str] | None:
    for sc in qualified:
        if sc.n < UPGRADE_MIN_OBS or success_rate(sc) >= UPGRADE_SUCCESS_THRESHOLD:
            continue
        idx = TIERS.index(sc.tier)
        if idx < len(TIERS) - 1:
            return (sc.tier, TIERS[idx + 1])
    return None

"""Summary-section rendering for recommendation report."""
from __future__ import annotations

from constants import MIN_OBS
from models import CellDecision


def summary_line(d: CellDecision) -> str:
    head = f"- {d.role} / {d.classification}: "
    if d.verdict == "LOCKED":
        return head + "LOCKED"
    if d.verdict == "INSUFFICIENT_DATA":
        return head + f"INSUFFICIENT_DATA ({d.max_n} obs, need {MIN_OBS})"
    if d.verdict == "DOWNGRADE":
        return head + f"DOWNGRADE {d.from_tier} → {d.to_tier}"
    if d.verdict == "UPGRADE":
        return head + f"UPGRADE {d.from_tier} → {d.to_tier}"
    return head + "NO CHANGE"

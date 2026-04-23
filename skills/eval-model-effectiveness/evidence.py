"""Evidence-section rendering for recommendation report."""
from __future__ import annotations

from constants import MIN_OBS, TIERS
from metrics import cost_per_success, success_rate
from models import CellDecision


def _row(sc) -> str:
    return (
        f"- {sc.tier}: {sc.n} obs, success_rate {success_rate(sc):.2f}, "
        f"cost/success ${cost_per_success(sc):.2f}"
    )


def _delta_line(d: CellDecision) -> str:
    cheap = next(s for s in d.subcells if s.tier == d.to_tier)
    exp = next(s for s in d.subcells if s.tier == d.from_tier)
    cps_exp = cost_per_success(exp)
    delta = (cost_per_success(cheap) - cps_exp) / cps_exp * 100 if cps_exp else 0.0
    return f"- cost delta (cheaper vs current): {delta:.1f}%"


def _confidence_flag(d: CellDecision) -> str:
    if d.verdict in ("INSUFFICIENT_DATA", "LOCKED"):
        return "N/A"
    return "HIGH" if d.max_n >= MIN_OBS else "LOW"


def evidence_block(d: CellDecision) -> list[str]:
    lines = [f"### {d.role} / {d.classification}"]
    lines.extend(_row(sc) for sc in sorted(d.subcells, key=lambda s: TIERS.index(s.tier)))
    if d.verdict == "DOWNGRADE":
        lines.append(_delta_line(d))
    lines.append(f"- confidence: {_confidence_flag(d)}")
    return lines

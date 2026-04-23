"""Success-rate and cost-per-success calculations."""
from __future__ import annotations

from constants import MAX_REVIEW_ROUNDS_OBS
from models import Subcell


def success_rate(sc: Subcell) -> float:
    n = sc.n
    if n == 0:
        return 0.0
    clean = sum(1 for o in sc.obs if o.review_rounds <= 1) / n
    no_rework = 1 - (sum(1 for o in sc.obs if o.rework) / n)
    avg_rounds = sum(o.review_rounds for o in sc.obs) / n
    rounds_term = MAX_REVIEW_ROUNDS_OBS / max(avg_rounds, 1)
    return clean * 0.6 + no_rework * 0.3 + rounds_term * 0.1


def cost_per_success(sc: Subcell) -> float:
    successes = sum(1 for o in sc.obs if not o.rework and o.review_rounds <= 2)
    return sc.total_cost / max(successes, 1)

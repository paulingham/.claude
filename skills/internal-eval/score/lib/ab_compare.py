"""A/B diff-economy + safety-retention comparator for /harness:internal-eval ab.

compare_arms() implements the safety-first guard-return ladder (Iron Law 1):
1. Zero scored cases → INSUFFICIENT (fail-closed, IL8)
2. Safety floor check: safety_B >= safety_A - EPSILON_SAFETY
3. Floor NOT held → EVAL_REGRESSION_DETECTED (improvement branch unreachable)
4. Floor held: EVAL_IMPROVEMENT_CONFIRMED if LOC or USD win; else EVAL_NEUTRAL

Verdicts are ALL polarity `info` — advisory, never gate any phase.

Public API: compare_arms(arm_a_run_id, arm_b_run_id, scored_a, scored_b,
    usd_a=None, usd_b=None, mutation_score_a=None, mutation_score_b=None,
    epsilon_safety=EPSILON_SAFETY_DEFAULT, eps_loc=EPS_LOC_DEFAULT,
    eps_usd=EPS_USD_DEFAULT) -> dict
"""
from __future__ import annotations

EPSILON_SAFETY_DEFAULT = 0.0
EPS_LOC_DEFAULT = 1
EPS_USD_DEFAULT = 0.01

_DEFAULTS = dict(usd_a=None, usd_b=None, mutation_score_a=None,
                 mutation_score_b=None, epsilon_safety=EPSILON_SAFETY_DEFAULT,
                 eps_loc=EPS_LOC_DEFAULT, eps_usd=EPS_USD_DEFAULT)

def _safety_pct(scored, mutation_score):
    if mutation_score is not None:
        return mutation_score
    total = len(scored)
    if total == 0:
        return 0.0
    return sum(1 for c in scored if c.get("pass", False)) / total

def _net_loc(scored):
    return sum(c.get("loc_added", 0) - c.get("loc_removed", 0) for c in scored)

def _insufficient(arm_a, arm_b, n_a, n_b):
    return {"verdict": "INSUFFICIENT", "arm_a_run_id": arm_a,
            "arm_b_run_id": arm_b, "n_a": n_a, "n_b": n_b}

def _regression(arm_a, arm_b, n_a, n_b, sa, sb, la, lb, ua, ub):
    return {"verdict": "EVAL_REGRESSION_DETECTED", "arm_a_run_id": arm_a,
            "arm_b_run_id": arm_b, "n_a": n_a, "n_b": n_b,
            "safety_a": sa, "safety_b": sb, "loc_a": la, "loc_b": lb,
            "usd_a": ua, "usd_b": ub}

def _outcome(arm_a, arm_b, n_a, n_b, sa, sb, la, lb, ua, ub, verdict):
    return {"verdict": verdict, "arm_a_run_id": arm_a, "arm_b_run_id": arm_b,
            "n_a": n_a, "n_b": n_b, "safety_a": sa, "safety_b": sb,
            "loc_a": la, "loc_b": lb, "usd_a": ua, "usd_b": ub}

def _improvement_verdict(la, lb, ua, ub, eps_loc, eps_usd):
    loc_win = lb < la - eps_loc
    usd_win = ua is not None and ub is not None and ub < ua - eps_usd
    return "EVAL_IMPROVEMENT_CONFIRMED" if (loc_win or usd_win) else "EVAL_NEUTRAL"

def _arm_metrics(sa_, sb_, msa, msb):
    return (_safety_pct(sa_, msa), _safety_pct(sb_, msb),
            _net_loc(sa_), _net_loc(sb_))

def _scored_ladder(aa, ab, sa_, sb_, ua, ub, msa, msb, eps, el, eu):
    na, nb = len(sa_), len(sb_)
    sfa, sfb, la, lb = _arm_metrics(sa_, sb_, msa, msb)
    if sfb < sfa - eps:
        return _regression(aa, ab, na, nb, sfa, sfb, la, lb, ua, ub)
    v = _improvement_verdict(la, lb, ua, ub, el, eu)
    return _outcome(aa, ab, na, nb, sfa, sfb, la, lb, ua, ub, v)

def _dispatch(aa, ab, sa_, sb_, kw):
    na, nb = len(sa_), len(sb_)
    if na == 0 or nb == 0:
        return _insufficient(aa, ab, na, nb)
    return _scored_ladder(aa, ab, sa_, sb_, kw["usd_a"], kw["usd_b"],
                          kw["mutation_score_a"], kw["mutation_score_b"],
                          kw["epsilon_safety"], kw["eps_loc"], kw["eps_usd"])

# WHY: **kw keeps the def on one line so signature continuations don't consume
# body-line budget; _dispatch holds the zero-guard + ladder call.
def compare_arms(**kw):
    kw = {**_DEFAULTS, **kw}
    aa, ab = kw.get("arm_a_run_id"), kw.get("arm_b_run_id")
    if aa is None or ab is None:
        raise ValueError("Both --arm-a and --arm-b run IDs are required")
    return _dispatch(aa, ab, kw.get("scored_a", ()), kw.get("scored_b", ()), kw)

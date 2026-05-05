"""Pure resolver for learned-instinct injection (Wave 4-M Slice 1).

Filters by role + confidence, dedups by id (instinct_dedup), sorts
confidence-desc then id-asc, caps at top_n, formats via instinct_format.
Returns "" when nothing survives.

C8 extension: when at least one anti-pattern survives the base filters,
the floor is boosted by +0.1 for non-anti-patterns. Anti-patterns
themselves are immune to the boost they trigger — they remain in the
survivor set regardless of confidence vs the boosted floor. Boost is
inline (no helper extraction); function stays small enough to read
top-to-bottom.
"""
from instinct_dedup import dedup_by_id
from instinct_env import resolve_min_confidence, resolve_top_n
from instinct_format import render


def _roles(instinct):
    roles = instinct["roles"]
    if not isinstance(roles, list):
        raise TypeError(f"instinct {instinct.get('id')!r} 'roles' must be list, got {type(roles).__name__}")
    return roles


def _filter_by_role(instincts, categories):
    cats = set(categories)
    return [i for i in instincts if set(_roles(i)) & cats]


def _filter_by_confidence(instincts, floor):
    return [i for i in instincts if i["confidence"] >= floor]


def _sort_and_top(instincts, n):
    return sorted(instincts, key=lambda i: (-i["confidence"], i["id"]))[:n]


def resolve_for_agent(agent_role, agent_instinct_categories, instincts,
                      min_confidence=0.4, top_n=5):
    if not isinstance(instincts, list):
        raise TypeError("instincts must be a list of dicts")
    cap = resolve_top_n(top_n)
    if cap == 0 or not agent_instinct_categories:
        return ""
    floor = resolve_min_confidence(min_confidence)
    after = _filter_by_role(instincts, agent_instinct_categories)
    after = _filter_by_confidence(after, floor)
    if any(i.get("category") == "anti-pattern" for i in after):
        after = [i for i in after if i.get("category") == "anti-pattern"
                 or i["confidence"] >= floor + 0.1]
    survivors = _sort_and_top(dedup_by_id(after), cap)
    return render(survivors) if survivors else ""

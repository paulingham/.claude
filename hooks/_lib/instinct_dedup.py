"""Dedup-by-id helper for instinct_injector (Wave 4-M Slice 1).

Same id seen twice: keep the higher-confidence entry. On confidence tie,
project-scope beats global-scope.
"""


def _prefer(cand, cur):
    if cand["confidence"] != cur["confidence"]:
        return cand["confidence"] > cur["confidence"]
    return cand.get("scope") == "project" and cur.get("scope") != "project"


def dedup_by_id(instincts):
    best = {}
    for i in instincts:
        if i["id"] not in best or _prefer(i, best[i["id"]]):
            best[i["id"]] = i
    return list(best.values())

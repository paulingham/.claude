"""Source dispatch helpers for search/timeline tiers."""
from recall._lib import search_tier, timeline_tier, envelope

_SEARCH = {"observations": search_tier.search_observations,
           "scratchpad":   search_tier.search_scratchpad}


def guarded(fn):
    def wrapped(*a, db_path=None, **kw):
        if envelope.db_missing(db_path):
            return []
        return fn(*a, db_path=db_path, **kw)
    return wrapped


def search(query, limit, source, db_path, include_private):
    pick = _SEARCH.get(source)
    if pick:
        return pick(db_path, query, limit, include_private)
    return _both(query, limit, db_path, include_private)


def _both(query, limit, db_path, include_private):
    obs = search_tier.search_observations(db_path, query, limit, include_private)
    sp = search_tier.search_scratchpad(db_path, query, limit, include_private)
    return [dict(h, source="observations") for h in obs] + sp


def timeline(limit, source, db_path, include_private):
    fn = (timeline_tier.fetch_scratchpad if source == "scratchpad"
          else timeline_tier.fetch_observations)
    return fn(db_path, "", (), limit, include_private)

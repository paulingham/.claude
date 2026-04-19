"""Source dispatch helpers for search/timeline tiers."""
from recall._lib import search_tier, timeline_tier, envelope, api_args

_SEARCH = {"observations": search_tier.search_observations,
           "scratchpad":   search_tier.search_scratchpad}
_TIMELINE = {"observations": timeline_tier.fetch_observations,
             "scratchpad":   timeline_tier.fetch_scratchpad}


def guarded(fn):
    def wrapped(*a, db_path=None, **kw):
        resolved = api_args.resolve_db(db_path)
        return _dispatch(fn, a, kw, resolved)
    return wrapped


def _dispatch(fn, a, kw, resolved):
    if envelope.db_missing(resolved):
        return []
    return fn(*a, db_path=resolved, **kw)


def search(query, limit, source, db_path, include_private, spec=None):
    if source == "both":
        return _search_both(query, limit, db_path, include_private, spec)
    return _SEARCH[source](db_path, query, limit, include_private, spec)


def _search_both(query, limit, db_path, include_private, spec):
    obs = [dict(h, source="observations") for h in _SEARCH["observations"](
        db_path, query, limit, include_private, spec)]
    sp = _SEARCH["scratchpad"](db_path, query, limit, include_private, spec)
    return (obs + sp)[:limit]


def timeline(limit, source, db_path, include_private, spec=None):
    if source == "both":
        return _timeline_both(limit, db_path, include_private, spec)
    return _TIMELINE[source](db_path, spec, limit, include_private)


def _timeline_both(limit, db_path, include_private, spec):
    obs = [dict(r, source="observations") for r in _TIMELINE["observations"](
        db_path, spec, limit, include_private)]
    sp = [dict(r, source="scratchpad") for r in _TIMELINE["scratchpad"](
        db_path, spec, limit, include_private)]
    return sorted(obs + sp, key=lambda r: r["timestamp"])[:limit]

"""Per-tool handlers that forward whitelisted args to recall + wrap envelope."""
from recall import recall
from recall._lib.envelope import envelope

_SEARCH_KEYS = ("query", "filters", "limit", "source", "db_path")
_TIMELINE_KEYS = ("filters", "limit", "source", "db_path")
_HYDRATE_KEYS = ("ids", "content_hashes", "db_path")


def search_memory(arguments):
    args = _pick(arguments, _SEARCH_KEYS)
    query = args.pop("query")
    limit = args.pop("limit", 20)
    return _wrap_paged("search", recall.search,
                       limit, (query,), args)


def get_timeline(arguments):
    args = _pick(arguments, _TIMELINE_KEYS)
    limit = args.pop("limit", 50)
    return _wrap_paged("timeline", recall.timeline, limit, (), args)


def get_observations(arguments):
    return _hydrate(recall.get_observations, arguments)


def get_findings(arguments):
    return _hydrate(recall.get_findings, arguments)


def _hydrate(fn, arguments):
    args = _pick(arguments, _HYDRATE_KEYS)
    hits = fn(**args)
    return envelope("hydrate", hits, len(hits), fetched=len(hits))


def _wrap_paged(tier, fn, limit, pos_args, kw):
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive int")
    raw = fn(*pos_args, limit=limit + 1, **kw)
    return envelope(tier, raw[:limit], limit, fetched=len(raw))


def _pick(arguments, keys):
    return {k: arguments[k] for k in keys if k in arguments}

"""Public API: search, timeline, get_observations, get_findings."""
from recall._lib import search_tier, timeline_tier, hydrate_tier, envelope


def search(query, *, filters=None, limit=20, source="both",
           db_path=None, include_private=False):
    if envelope.db_missing(db_path):
        return []
    return _dispatch_search(query, limit, source, db_path, include_private)


def _dispatch_search(query, limit, source, db_path, include_private):
    if source == "observations":
        return search_tier.search_observations(
            db_path, query, limit, include_private)
    return []


def timeline(*, filters=None, limit=50, source="observations",
             db_path=None, include_private=False):
    if envelope.db_missing(db_path):
        return []
    return timeline_tier.fetch_observations(
        db_path, "", (), limit, include_private)


def get_observations(*, ids=None, content_hashes=None,
                     db_path=None, include_private=False):
    if envelope.db_missing(db_path):
        return []
    return hydrate_tier.fetch_by_ids(db_path, ids or [], include_private)


def get_findings(*, ids=None, content_hashes=None,
                 db_path=None, include_private=False):
    if envelope.db_missing(db_path):
        return []
    return []

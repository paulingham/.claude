"""Public API: search, timeline, get_observations, get_findings."""
from recall._lib import dispatch, hydrate_tier


@dispatch.guarded
def search(query, *, filters=None, limit=20, source="both",
           db_path=None, include_private=False):
    return dispatch.search(query, limit, source, db_path, include_private)


@dispatch.guarded
def timeline(*, filters=None, limit=50, source="observations",
             db_path=None, include_private=False):
    return dispatch.timeline(limit, source, db_path, include_private)


@dispatch.guarded
def get_observations(*, ids=None, content_hashes=None,
                     db_path=None, include_private=False):
    return hydrate_tier.fetch_by_ids(db_path, ids or [], include_private)


@dispatch.guarded
def get_findings(*, ids=None, content_hashes=None,
                 db_path=None, include_private=False):
    return hydrate_tier.fetch_findings_by_ids(
        db_path, ids or [], include_private)

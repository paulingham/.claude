"""Public API: search, timeline, get_observations, get_findings."""
from recall._lib import dispatch, hydrate_tier, api_args


@dispatch.guarded
def search(query, *, filters=None, limit=20, source="both",
           db_path=None, include_private=False):
    api_args.check_source(source)
    return api_args.guarded_call(
        dispatch.search, query, api_args.clamp_limit(limit),
        source, db_path, include_private, filters)


@dispatch.guarded
def timeline(*, filters=None, limit=50, source="observations",
             db_path=None, include_private=False):
    api_args.check_source(source)
    return api_args.guarded_call(
        dispatch.timeline, api_args.clamp_limit(limit), source,
        db_path, include_private, filters)


@dispatch.guarded
def get_observations(*, ids=None, content_hashes=None,
                     db_path=None, include_private=False):
    return _hydrate(hydrate_tier.fetch_by_ids,
                    hydrate_tier.fetch_by_hashes,
                    db_path, ids, content_hashes, include_private)


@dispatch.guarded
def get_findings(*, ids=None, content_hashes=None,
                 db_path=None, include_private=False):
    return _hydrate(hydrate_tier.fetch_findings_by_ids,
                    hydrate_tier.fetch_findings_by_hashes,
                    db_path, ids, content_hashes, include_private)


def _hydrate(by_ids, by_hashes, db_path, ids, hashes, include_private):
    if not ids and not hashes:
        raise ValueError("supply ids or content_hashes")
    if hashes:
        return by_hashes(db_path, api_args.cap_ids(hashes), include_private)
    return by_ids(db_path, api_args.cap_ids(ids), include_private)

"""Tier 1: FTS5 search across observations + scratchpad_findings."""
from recall._lib import connect, filters

_OBS_SQL = (
    "SELECT o.id AS id, o.content_hash AS content_hash, "
    "o.timestamp AS timestamp, o.tool AS tool, o.file AS file, "
    "snippet(observations_fts, 0, '[', ']', '…', 8) AS snippet "
    "FROM observations_fts "
    "JOIN observations o ON o.id = observations_fts.rowid "
    "WHERE observations_fts MATCH ?{priv} {where}"
    "ORDER BY bm25(observations_fts) LIMIT ?")

_SP_SQL = (
    "SELECT s.id AS id, s.content_hash AS content_hash, "
    "s.timestamp AS timestamp, s.category AS category, "
    "snippet(scratchpad_fts, 0, '[', ']', '…', 8) AS snippet, "
    "'scratchpad' AS source "
    "FROM scratchpad_fts "
    "JOIN scratchpad_findings s ON s.id = scratchpad_fts.rowid "
    "WHERE scratchpad_fts MATCH ?{priv} {where}"
    "ORDER BY bm25(scratchpad_fts) LIMIT ?")


def search_observations(db_path, query, limit=20, include_private=False,
                        filter_spec=None):
    where, binds = filters.resolve("observations", filter_spec)
    sql = _fmt(_OBS_SQL, "o", include_private, where)
    return _run(db_path, sql, (query, *binds, limit))


def search_scratchpad(db_path, query, limit=20, include_private=False,
                      filter_spec=None):
    where, binds = filters.resolve("scratchpad", filter_spec)
    sql = _fmt(_SP_SQL, "s", include_private, where)
    return _run(db_path, sql, (query, *binds, limit))


def _fmt(sql, alias, include_private, where):
    priv = "" if include_private else f" AND {alias}.is_private = 0"
    clause = f" {where} " if where else " "
    return sql.replace("{priv}", priv).replace(" {where}", clause)


def _run(db_path, sql, params):
    con = connect.read_only(db_path)
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()

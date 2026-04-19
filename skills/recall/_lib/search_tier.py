"""Tier 1: FTS5 search across observations + scratchpad_findings."""
from recall._lib import connect

_OBS_SQL = (
    "SELECT o.id AS id, o.content_hash AS content_hash, "
    "o.timestamp AS timestamp, o.tool AS tool, o.file AS file, "
    "snippet(observations_fts, 0, '[', ']', '…', 8) AS snippet "
    "FROM observations_fts "
    "JOIN observations o ON o.id = observations_fts.rowid "
    "WHERE observations_fts MATCH ?{priv} "
    "ORDER BY bm25(observations_fts) LIMIT ?")


def search_observations(db_path, query, limit=20, include_private=False):
    priv = "" if include_private else " AND o.is_private = 0"
    sql = _OBS_SQL.replace("{priv}", priv)
    return _run(db_path, sql, (query, limit))


def _run(db_path, sql, params):
    con = connect.read_only(db_path)
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()

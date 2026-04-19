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

_SP_SQL = (
    "SELECT s.id AS id, s.content_hash AS content_hash, "
    "s.timestamp AS timestamp, s.category AS category, "
    "snippet(scratchpad_fts, 0, '[', ']', '…', 8) AS snippet, "
    "'scratchpad' AS source "
    "FROM scratchpad_fts "
    "JOIN scratchpad_findings s ON s.id = scratchpad_fts.rowid "
    "WHERE scratchpad_fts MATCH ?{priv} "
    "ORDER BY bm25(scratchpad_fts) LIMIT ?")


def search_observations(db_path, query, limit=20, include_private=False):
    sql = _OBS_SQL.replace("{priv}", _priv("o", include_private))
    return _run(db_path, sql, (query, limit))


def search_scratchpad(db_path, query, limit=20, include_private=False):
    sql = _SP_SQL.replace("{priv}", _priv("s", include_private))
    return _run(db_path, sql, (query, limit))


def _priv(alias, include_private):
    return "" if include_private else f" AND {alias}.is_private = 0"


def _run(db_path, sql, params):
    con = connect.read_only(db_path)
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()

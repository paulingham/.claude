"""Tier 3: hydrate full observation/finding rows by id or content_hash."""
from recall._lib import connect

_OBS_COLS = ("id", "content_hash", "session_id", "project_hash", "timestamp",
             "tool", "file", "phase", "agent_role", "outcome", "is_private")


def fetch_by_ids(db_path, ids, include_private=False):
    return _fetch(db_path, "id", ids, include_private)


def _fetch(db_path, col, values, include_private):
    if not values:
        return []
    con = connect.read_only(db_path)
    try:
        return _query(con, col, values, include_private)
    finally:
        con.close()


def _query(con, col, values, include_private):
    marks = ",".join("?" * len(values))
    priv = "" if include_private else " AND is_private = 0"
    sql = (f"SELECT {','.join(_OBS_COLS)} FROM observations "
           f"WHERE {col} IN ({marks}){priv}")
    return [dict(r) for r in con.execute(sql, values).fetchall()]

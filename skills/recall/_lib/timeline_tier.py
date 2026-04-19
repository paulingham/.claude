"""Tier 2: timeline — ordered rows from observations/scratchpad_findings."""
from recall._lib import connect

_OBS_COLS = ("id", "timestamp", "tool", "file", "outcome")


def fetch_observations(db_path, where="", params=(), limit=50,
                       include_private=False):
    priv = "" if include_private else " AND is_private = 0"
    sql = (f"SELECT {','.join(_OBS_COLS)} FROM observations "
           f"WHERE 1=1{where}{priv} ORDER BY timestamp ASC LIMIT ?")
    return _run(db_path, sql, (*params, limit))


def _run(db_path, sql, params):
    con = connect.read_only(db_path)
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()


def explain_observations(db_path):
    sql = (f"EXPLAIN QUERY PLAN SELECT {','.join(_OBS_COLS)} "
           "FROM observations WHERE is_private = 0 "
           "ORDER BY timestamp ASC LIMIT 50")
    return _run(db_path, sql, ())

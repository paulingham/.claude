"""Tier 2: timeline — ordered rows from observations/scratchpad_findings."""
from recall._lib import connect, filters

_OBS_COLS = ("id", "session_id", "timestamp", "tool", "file", "outcome")
_SP_COLS = ("id", "timestamp", "category", "agent_role", "phase", "task_id")


def fetch_observations(db_path, filter_spec=None, limit=50,
                       include_private=False):
    where, binds = filters.resolve("observations", filter_spec)
    return _fetch("observations", _OBS_COLS, db_path, where, binds,
                  limit, include_private)


def fetch_scratchpad(db_path, filter_spec=None, limit=50,
                     include_private=False):
    where, binds = filters.resolve("scratchpad", filter_spec)
    return _fetch("scratchpad_findings", _SP_COLS, db_path, where,
                  binds, limit, include_private)


def _fetch(table, cols, db_path, where, binds, limit, include_private):
    priv = "" if include_private else " AND is_private = 0"
    sql = (f"SELECT {','.join(cols)} FROM {table} "
           f"WHERE 1=1 {where}{priv} ORDER BY timestamp ASC LIMIT ?")
    return _run(db_path, sql, (*binds, limit))


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

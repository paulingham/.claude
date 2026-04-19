"""Tier 3: hydrate full observation/finding rows by id or content_hash."""
from recall._lib import connect

_OBS_COLS = ("id", "content_hash", "session_id", "project_hash", "timestamp",
             "tool", "file", "phase", "agent_role", "outcome", "is_private")
_SP_COLS = ("id", "content_hash", "task_id", "category", "agent_role",
            "phase", "timestamp", "body", "is_private")


def fetch_by_ids(db_path, ids, include_private=False):
    return _fetch(db_path, "observations", _OBS_COLS, "id", ids,
                  include_private)


def fetch_by_hashes(db_path, hashes, include_private=False):
    return _fetch(db_path, "observations", _OBS_COLS, "content_hash",
                  hashes, include_private)


def fetch_findings_by_ids(db_path, ids, include_private=False):
    return _fetch(db_path, "scratchpad_findings", _SP_COLS, "id", ids,
                  include_private)


def fetch_findings_by_hashes(db_path, hashes, include_private=False):
    return _fetch(db_path, "scratchpad_findings", _SP_COLS,
                  "content_hash", hashes, include_private)


def _fetch(db_path, table, cols, col, values, include_private):
    if not values:
        return []
    return _with_con(db_path, table, cols, col, values, include_private)


def _with_con(db_path, table, cols, col, values, include_private):
    con = connect.read_only(db_path)
    try:
        return _query(con, table, cols, col, values, include_private)
    finally:
        con.close()


def _query(con, table, cols, col, values, include_private):
    marks = ",".join("?" * len(values))
    priv = "" if include_private else " AND is_private = 0"
    sql = (f"SELECT {','.join(cols)} FROM {table} "
           f"WHERE {col} IN ({marks}){priv}")
    return [dict(r) for r in con.execute(sql, values).fetchall()]

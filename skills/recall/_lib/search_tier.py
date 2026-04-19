"""Tier 1: FTS5 search across observations + scratchpad_findings."""
import sqlite3
import sys
from recall._lib import connect, filters, search_sql


def search_observations(db_path, query, limit=20, include_private=False,
                        filter_spec=None):
    where, binds = filters.resolve("observations", filter_spec)
    sql = _fmt(search_sql.OBS, "o", include_private, where)
    return _safe_run(db_path, sql, (query, *binds, limit))


def search_scratchpad(db_path, query, limit=20, include_private=False,
                      filter_spec=None):
    where, binds = filters.resolve("scratchpad", filter_spec)
    sql = _fmt(search_sql.SP, "s", include_private, where)
    return _safe_run(db_path, sql, (query, *binds, limit))


def _fmt(sql, alias, include_private, where):
    priv = "" if include_private else f" AND {alias}.is_private = 0"
    clause = f" {where} " if where else " "
    return sql.replace("{priv}", priv).replace(" {where}", clause)


def _safe_run(db_path, sql, params):
    try:
        return _run(db_path, sql, params)
    except sqlite3.OperationalError:
        sys.stderr.write("recall: invalid search query\n")
        return []


def _run(db_path, sql, params):
    con = connect.read_only(db_path)
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()

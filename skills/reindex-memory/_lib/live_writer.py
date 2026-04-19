"""Live SQLite writer for PostToolUse hook. Reuses S1 hash + row shape."""
import json
import sqlite3
import sys
from pathlib import Path

from _lib import paths, rows, embed_gate, findings, _privacy_wire


def write_one(obj, db_path=None):
    target = Path(db_path) if db_path else paths.default_db()
    with sqlite3.connect(str(target), timeout=5.0) as con:
        return _insert(con, obj, target)


def write_finding(obj, db_path=None):
    target = Path(db_path) if db_path else paths.default_db()
    with sqlite3.connect(str(target), timeout=5.0) as con:
        return _insert_finding(con, obj)


def _insert_finding(con, obj):
    row = findings.row_from_obj(_privacy_wire.apply(obj))
    return con.execute(findings.INSERT_SQL, row).rowcount


def _insert(con, obj, target):
    sanitized = _privacy_wire.apply(obj)
    row = rows.row_from_obj(sanitized, target)
    cur = con.execute(rows.INSERT_SQL, row)
    embed_gate.maybe_embed(con, sanitized, row[0])
    return cur.rowcount


def main():
    write_one(json.loads(sys.stdin.read()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

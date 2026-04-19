"""Live SQLite writer for PostToolUse hook. Reuses S1 hash + row shape."""
import json
import sqlite3
import sys
from pathlib import Path

from _lib import paths, rows


def write_one(obj, db_path=None):
    target = Path(db_path) if db_path else paths.default_db()
    with sqlite3.connect(str(target), timeout=1.0) as con:
        return _insert(con, obj, target)


def _insert(con, obj, target):
    cur = con.execute(rows.INSERT_SQL, rows.row_from_obj(obj, target))
    return cur.rowcount


def main():
    write_one(json.loads(sys.stdin.read()))
    return 0


if __name__ == "__main__":
    sys.exit(main())

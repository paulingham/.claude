"""Live SQLite writer for PostToolUse hook. Reuses S1 hash + row shape."""
import json
import sqlite3
import sys
from pathlib import Path

from _lib import paths, rows


def write_one(obj, db_path=None):
    """Insert one observation row. Returns rowcount (0 if dedup'd)."""
    target = Path(db_path) if db_path else paths.default_db()
    con = sqlite3.connect(str(target), timeout=1.0)
    try:
        return _insert(con, obj, target)
    finally:
        con.close()


def _insert(con, obj, target):
    cur = con.execute(rows.INSERT_SQL, rows.row_from_obj(obj, target))
    con.commit()
    return cur.rowcount


def main():
    """CLI: read one JSON object from stdin, insert into default DB."""
    obj = json.loads(sys.stdin.read())
    write_one(obj)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Walk learning/*/observations.jsonl and insert rows into SQLite."""
import sqlite3
import sys
from dataclasses import dataclass

from _lib import jsonl, rows


@dataclass
class Summary:
    inserted: int = 0
    skipped: int = 0
    bad: int = 0


def ingest_all(db_path, learning_root):
    summary = Summary()
    files = sorted(learning_root.glob("*/observations.jsonl"))
    con = sqlite3.connect(str(db_path))
    try:
        for path in files:
            _ingest_one(con, path, summary)
        con.commit()
    finally:
        con.close()
    return summary


def _ingest_one(con, path, summary):
    for obj in jsonl.parse_file(path, on_error=_err_handler(summary)):
        _insert_row(con, obj, path, summary)


def _err_handler(summary):
    def _on(path, pos, exc):
        summary.bad += 1
        print(f"skip {path}:{pos}: {exc}", file=sys.stderr)
    return _on


def _insert_row(con, obj, path, summary):
    cur = con.execute(rows.INSERT_SQL, rows.row_from_obj(obj, path))
    if cur.rowcount:
        summary.inserted += 1
    else:
        summary.skipped += 1

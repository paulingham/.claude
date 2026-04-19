"""Walk learning/*/observations.jsonl and insert rows into SQLite."""
import sqlite3
from dataclasses import dataclass

from _lib import jsonl, rows


@dataclass
class Summary:
    inserted: int = 0
    skipped: int = 0
    bad: int = 0


_INSERT_SQL = (
    "INSERT OR IGNORE INTO observations (" + ",".join(rows.COLS) +
    ") VALUES (" + ",".join(["?"] * len(rows.COLS)) + ")")


def ingest_all(db_path, learning_root, verbose=False):
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
    for obj in jsonl.parse_file(path, on_error=lambda *a: _bump_bad(summary)):
        _insert_row(con, obj, path, summary)


def _insert_row(con, obj, path, summary):
    cur = con.execute(_INSERT_SQL, rows.row_from_obj(obj, path))
    if cur.rowcount:
        summary.inserted += 1
    else:
        summary.skipped += 1


def _bump_bad(summary):
    summary.bad += 1

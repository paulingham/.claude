"""Read-only SQLite connector (URI mode, no writes)."""
import sqlite3
from pathlib import Path

_FORBIDDEN = set("?#&\n")


def read_only(db_path):
    """Open db_path as read-only; caller closes."""
    resolved = _safe_path(db_path)
    con = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only = 1")
    return con


def _safe_path(db_path):
    raw = str(db_path)
    if _FORBIDDEN & set(raw):
        raise ValueError("invalid db_path")
    return Path(raw).resolve(strict=True)

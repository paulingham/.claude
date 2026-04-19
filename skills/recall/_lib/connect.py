"""Read-only SQLite connector (URI mode, no writes)."""
import sqlite3


def read_only(db_path):
    """Open db_path as read-only; caller closes."""
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con

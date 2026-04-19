"""Read-only fetch of stored embeddings by content_hash."""
import sqlite3


def load(db_path, hashes):
    if not hashes:
        return {}
    con = _open_ro(db_path)
    try:
        return _fetch(con, hashes)
    finally:
        con.close()


def _open_ro(db_path):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.execute("PRAGMA query_only = 1")
    return con


def _fetch(con, hashes):
    placeholders = ",".join(["?"] * len(hashes))
    sql = (f"SELECT content_hash, vector FROM embeddings "
           f"WHERE content_hash IN ({placeholders})")
    return {h: v for h, v in con.execute(sql, hashes).fetchall()}

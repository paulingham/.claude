"""Count rows without matching embeddings row. Read-only, missing-DB safe."""
import os
import sqlite3
import sys
from pathlib import Path

_LIB_DIR = str(Path(__file__).parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from harness_paths import harness_data  # noqa: E402

_DEFAULT_DB = harness_data() / "db" / "memory.sqlite"


def db_path():
    return Path(os.environ.get("CLAUDE_DB_PATH") or _DEFAULT_DB)


def unembedded_count():
    path = db_path()
    if not path.exists():
        return 0
    return _count_read_only(path)


def _count_read_only(path):
    uri = f"file:{path}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        return _sum_tables(con)
    finally:
        con.close()


def _sum_tables(con):
    return _missing(con, "observations") + _missing(con, "scratchpad_findings")


def _missing(con, table):
    try:
        row = con.execute(
            f"SELECT COUNT(*) FROM {table} t "
            f"WHERE NOT EXISTS (SELECT 1 FROM embeddings e "
            f"WHERE e.content_hash = t.content_hash)").fetchone()
    except sqlite3.OperationalError:
        return 0
    return row[0] if row else 0

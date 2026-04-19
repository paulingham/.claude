"""Apply db/schema.sql, detect drift, rebuild data tables when needed."""
import sqlite3
from pathlib import Path

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "db" / "schema.sql"
CURRENT_VERSION = 1
_DATA_TABLES = ("observations", "observations_fts",
                "scratchpad_findings", "scratchpad_fts")


def ensure(db_path):
    """Create DB + schema; rebuild data tables when schema version drifted."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    existed = Path(db_path).exists()
    con = sqlite3.connect(str(db_path))
    try:
        if existed and _read_version(con) < CURRENT_VERSION:
            _drop_data_tables(con)
        con.executescript(SCHEMA_SQL.read_text())
        con.commit()
    finally:
        con.close()


def _read_version(con):
    try:
        row = con.execute(
            "SELECT MAX(version) FROM schema_version").fetchone()
    except sqlite3.OperationalError:
        return 0
    return (row[0] or 0) if row else 0


def _drop_data_tables(con):
    for t in _DATA_TABLES:
        con.execute(f"DROP TABLE IF EXISTS {t}")
    con.execute("DELETE FROM schema_version")


def prune_orphan_embeddings(db_path):
    """Delete embeddings whose content_hash has no matching row."""
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(
            "DELETE FROM embeddings WHERE content_hash NOT IN "
            "(SELECT content_hash FROM observations "
            "UNION SELECT content_hash FROM scratchpad_findings)")
        con.commit()
    finally:
        con.close()

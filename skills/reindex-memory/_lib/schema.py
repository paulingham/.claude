"""Apply db/schema.sql, detect drift, rebuild data tables when needed."""
import sqlite3
from pathlib import Path

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "db" / "schema.sql"
CURRENT_VERSION = 1
_TABLES = ("observations", "observations_fts",
           "scratchpad_findings", "scratchpad_fts")


def ensure(db_path):
    """Create DB + schema; return True when data tables were rebuilt."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    existed = Path(db_path).exists()
    con = sqlite3.connect(str(db_path))
    try:
        return _apply(con, existed)
    finally:
        con.close()


def _apply(con, existed):
    rebuilt = existed and _read_version(con) < CURRENT_VERSION
    if rebuilt:
        _drop_data_tables(con)
    con.executescript(SCHEMA_SQL.read_text())
    con.commit()
    return rebuilt


def _read_version(con):
    try:
        row = con.execute(
            "SELECT MAX(version) FROM schema_version").fetchone()
    except sqlite3.OperationalError:
        return 0
    return (row[0] or 0) if row else 0


def _drop_data_tables(con):
    for t in _TABLES:
        con.execute(f"DROP TABLE IF EXISTS {t}")
    con.execute("DELETE FROM schema_version")

"""Apply db/schema.sql to a target SQLite database."""
import sqlite3
from pathlib import Path

SCHEMA_SQL = Path(__file__).resolve().parents[3] / "db" / "schema.sql"
CURRENT_VERSION = 1


def ensure(db_path):
    """Create parent dir + apply schema. Idempotent."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.executescript(SCHEMA_SQL.read_text())
        con.commit()
    finally:
        con.close()


def read_version(db_path):
    """Return the highest schema_version.version, or 0 if absent."""
    con = sqlite3.connect(str(db_path))
    try:
        row = con.execute("SELECT MAX(version) FROM schema_version").fetchone()
    finally:
        con.close()
    return row[0] or 0

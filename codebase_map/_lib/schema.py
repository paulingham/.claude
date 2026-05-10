"""SQLite cache schema for codebase-map tags.

Mirrors `skills/reindex-memory/_lib/schema.py:1-44` shape: WAL pragma,
schema_version table, idempotent ensure_cache, drop+rebuild on drift.

Concurrency contract (AC3-bis): the schema-version write uses
`INSERT OR IGNORE` so two threads racing into ensure_cache() converge
to a single schema_version row without a process-level flock. This is
WAL-safe; SQLite serialises single-row inserts atomically. Direct
`python3 -m codebase_map.cli build` calls bypassing the harness hook
are not safe at the GENERATOR layer — Slice C's `with_codebase_map_lock`
is the canonical generator-invocation serialisation point.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL,
  notes TEXT
);
INSERT OR IGNORE INTO schema_version (version, applied_at, notes)
  VALUES ({version}, datetime('now'), 'codebase-map slice A initial schema');

CREATE TABLE IF NOT EXISTS tags (
  file TEXT NOT NULL,
  mtime REAL NOT NULL,
  kind TEXT NOT NULL,
  name TEXT NOT NULL,
  line INTEGER NOT NULL,
  col INTEGER NOT NULL,
  lang TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tags_file ON tags(file);
CREATE INDEX IF NOT EXISTS idx_tags_file_mtime ON tags(file, mtime);
""".format(version=SCHEMA_VERSION)

_DATA_TABLES = ("tags",)


def ensure_cache(db_path: Path) -> bool:
    """Create or migrate the cache DB. Return True iff data was rebuilt.

    Idempotent on repeated calls. Concurrent calls converge atomically
    via WAL-safe INSERT OR IGNORE on schema_version.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    existed = Path(db_path).exists()
    con = sqlite3.connect(str(db_path))
    try:
        return _apply(con, existed)
    finally:
        con.close()


def _apply(con: sqlite3.Connection, existed: bool) -> bool:
    rebuilt = existed and _read_version(con) < SCHEMA_VERSION
    if rebuilt:
        _drop_data_tables(con)
    con.executescript(_SCHEMA_SQL)
    con.commit()
    return rebuilt


def _read_version(con: sqlite3.Connection) -> int:
    try:
        row = con.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    return (row[0] or 0) if row else 0


def _drop_data_tables(con: sqlite3.Connection) -> None:
    for table in _DATA_TABLES:
        con.execute(f"DROP TABLE IF EXISTS {table}")
    con.execute("DELETE FROM schema_version")

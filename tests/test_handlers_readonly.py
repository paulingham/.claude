"""Read-only invariant across all four MCP handlers (AC8)."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mcp_support  # noqa: F401,E402
from _support import build_populated_db, count_rows, insert_scratchpad_rows  # noqa: E402
from mcp_memory._lib import handlers  # noqa: E402


class TestReadOnlyInvariant(unittest.TestCase):
    def test_five_rounds_mutate_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, [{
                "hash": "ro1", "task": "t", "cat": "pattern",
                "role": "eng", "phase": "build",
                "ts": "2026-04-01T10:00:00Z",
                "body": "read only body", "priv": 0}])
            before = _snapshot(db)
            for _ in range(5):
                _exercise_all(db)
            self.assertEqual(_snapshot(db), before)


def _exercise_all(db):
    handlers.search_memory({"query": "Read", "db_path": str(db)})
    handlers.get_timeline({"source": "both", "db_path": str(db)})
    handlers.get_observations({"ids": [1], "db_path": str(db)})
    handlers.get_findings({"ids": [1], "db_path": str(db)})


def _snapshot(db):
    tables = ("observations", "observations_fts",
              "scratchpad_findings", "embeddings")
    schema = _schema_sql(db)
    return (tuple(count_rows(db, t) for t in tables), schema)


def _schema_sql(db):
    con = sqlite3.connect(str(db))
    try:
        return tuple(con.execute(
            "SELECT sql FROM sqlite_master ORDER BY name").fetchall())
    finally:
        con.close()


if __name__ == "__main__":
    unittest.main()

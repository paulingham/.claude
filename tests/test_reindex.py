"""Acceptance-criterion tests for reindex.py."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills" / "reindex-memory"))

import reindex  # noqa: E402


def _list_tables(db_path):
    con = sqlite3.connect(str(db_path))
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type IN ('table','virtual') OR sql LIKE '%VIRTUAL%'"
        ).fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _fixture_rows():
    return [
        {"session_id": "s1", "timestamp": "2026-04-01T00:00:00Z",
         "tool": "Read", "file": "/a.py", "outcome": "success"},
        {"session_id": "s1", "timestamp": "2026-04-01T00:00:01Z",
         "tool": "Edit", "file": "/a.py", "outcome": "success"},
        {"session_id": "s2", "timestamp": "2026-04-01T00:00:02Z",
         "tool": "Bash", "file": "", "outcome": "success"},
    ]


class AC1SchemaCreated(unittest.TestCase):
    def test_creates_db_with_all_tables_and_version_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            learning = Path(tmp) / "learning"
            learning.mkdir()
            reindex.run(db_path=db, learning_root=learning)
            expected = {"observations", "observations_fts",
                        "scratchpad_findings", "scratchpad_fts",
                        "embeddings", "privacy_allowlist", "schema_version"}
            self.assertTrue(expected.issubset(_list_tables(db)))
            con = sqlite3.connect(str(db))
            try:
                ver = con.execute(
                    "SELECT version FROM schema_version").fetchone()[0]
            finally:
                con.close()
            self.assertEqual(ver, 1)


class AC2NRowsInserted(unittest.TestCase):
    def test_jsonl_rows_populate_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            learning = Path(tmp) / "learning"
            _write_jsonl(learning / "pha" / "observations.jsonl",
                         _fixture_rows())
            reindex.run(db_path=db, learning_root=learning)
            con = sqlite3.connect(str(db))
            try:
                count = con.execute(
                    "SELECT COUNT(*) FROM observations").fetchone()[0]
            finally:
                con.close()
            self.assertEqual(count, 3)


if __name__ == "__main__":
    unittest.main()

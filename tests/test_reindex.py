"""Acceptance-criterion tests for reindex.py."""
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
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


def _count(db, table):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        con.close()


def _build_populated_db(tmp):
    db = Path(tmp) / "memory.sqlite"
    learning = Path(tmp) / "learning"
    _write_jsonl(learning / "pha" / "observations.jsonl", _fixture_rows())
    reindex.run(db_path=db, learning_root=learning)
    return db, learning


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
            db, _ = _build_populated_db(tmp)
            self.assertEqual(_count(db, "observations"), 3)


class AC3IdempotentDedup(unittest.TestCase):
    def test_second_run_inserts_zero_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, learning = _build_populated_db(tmp)
            before = _count(db, "observations")
            summary = reindex.run(db_path=db, learning_root=learning)
            self.assertEqual(_count(db, "observations"), before)
            self.assertEqual(summary.inserted, 0)
            self.assertEqual(summary.skipped, 3)


class AC4MalformedRowsSkipped(unittest.TestCase):
    def test_bad_rows_logged_good_rows_inserted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            learning = Path(tmp) / "learning"
            p = learning / "pha" / "observations.jsonl"
            p.parent.mkdir(parents=True)
            p.write_text('{"session_id":"s1","timestamp":"t1","tool":"Read"}\n'
                         'not json at all\n'
                         '{"session_id":"s2","timestamp":"t2","tool":"Edit"}\n')
            err = io.StringIO()
            with redirect_stderr(err):
                summary = reindex.run(db_path=db, learning_root=learning)
            self.assertEqual(_count(db, "observations"), 2)
            self.assertGreaterEqual(summary.bad, 1)
            self.assertIn("skip", err.getvalue())


class AC4ExitCodeZero(unittest.TestCase):
    def test_main_returns_zero_when_bad_rows_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            learning = Path(tmp) / "learning"
            p = learning / "pha" / "observations.jsonl"
            p.parent.mkdir(parents=True)
            p.write_text('not json\n{"tool":"X","timestamp":"t",'
                         '"session_id":"s"}\n')
            err, out = io.StringIO(), io.StringIO()
            with redirect_stderr(err), redirect_stdout(out):
                rc = reindex.main(
                    ["--db", str(db), "--learning", str(learning)])
            self.assertEqual(rc, 0)


class AC5SchemaDriftRebuild(unittest.TestCase):
    def _seed_stale(self, db, surviving_hash):
        con = sqlite3.connect(str(db))
        con.execute(
            "INSERT INTO embeddings (content_hash, model_id, dim, vector) "
            "VALUES (?, 'bge-small-en-v1.5', 384, ?)",
            (surviving_hash, b"\x00" * 1536))
        con.execute(
            "INSERT INTO embeddings (content_hash, model_id, dim, vector) "
            "VALUES ('orphan_hash_xxx', 'bge-small-en-v1.5', 384, ?)",
            (b"\x01" * 1536,))
        con.execute("UPDATE schema_version SET version = 0 WHERE version = 1")
        con.commit()
        con.close()

    def test_drift_drops_observations_preserves_mapped_embeddings(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, learning = _build_populated_db(tmp)
            surviving = sqlite3.connect(str(db)).execute(
                "SELECT content_hash FROM observations LIMIT 1").fetchone()[0]
            self._seed_stale(db, surviving)
            reindex.run(db_path=db, learning_root=learning)
            self.assertEqual(_count(db, "observations"), 3)
            # surviving content_hash retained, orphan dropped
            con = sqlite3.connect(str(db))
            try:
                surv_kept = con.execute(
                    "SELECT COUNT(*) FROM embeddings WHERE content_hash=?",
                    (surviving,)).fetchone()[0]
                orphan_kept = con.execute(
                    "SELECT COUNT(*) FROM embeddings "
                    "WHERE content_hash='orphan_hash_xxx'").fetchone()[0]
                ver = con.execute(
                    "SELECT MAX(version) FROM schema_version").fetchone()[0]
            finally:
                con.close()
            self.assertEqual(surv_kept, 1)
            self.assertEqual(orphan_kept, 0)
            self.assertEqual(ver, 1)


class AC6FTSPlausible(unittest.TestCase):
    def test_fts_query_returns_nonneg_integer(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = _build_populated_db(tmp)
            con = sqlite3.connect(str(db))
            try:
                n = con.execute(
                    "SELECT COUNT(*) FROM observations_fts "
                    "WHERE observations_fts MATCH 'Read'").fetchone()[0]
            finally:
                con.close()
            self.assertIsInstance(n, int)
            self.assertGreaterEqual(n, 1)


if __name__ == "__main__":
    unittest.main()

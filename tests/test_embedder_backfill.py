"""Slice 13: backfill CLI — idempotent, privacy-aware, summary line."""
import io
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / "skills"))

from _support import build_populated_db  # noqa: E402


def _count(db, sql, *args):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(sql, args).fetchone()[0]
    finally:
        con.close()


def _run_backfill_api(db):
    os.environ["CLAUDE_EMBEDDER"] = "fake"
    try:
        from embedder import backfill as bf
        return bf.run(db_path=db)
    finally:
        os.environ.pop("CLAUDE_EMBEDDER", None)


class BackfillIdempotent(unittest.TestCase):
    def test_second_run_inserts_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            first = _run_backfill_api(db)
            self.assertGreater(first["inserted"], 0)
            second = _run_backfill_api(db)
            self.assertEqual(second["inserted"], 0)


class BackfillIncludesPrivateRows(unittest.TestCase):
    def test_private_observation_gets_embedding(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            _insert_private_row(db)
            _run_backfill_api(db)
            self.assertEqual(_count(db,
                "SELECT COUNT(*) FROM embeddings WHERE content_hash = ?",
                "privhash1"), 1)


class BackfillPrivacyCommentInSource(unittest.TestCase):
    def test_source_contains_privacy_note(self):
        src = (REPO_ROOT / "skills" / "embedder"
               / "backfill.py").read_text()
        self.assertIn("privacy is enforced at recall", src.lower())


class BackfillSummaryToStdout(unittest.TestCase):
    def test_stdout_contains_backfill_summary_line(self):
        os.environ["CLAUDE_EMBEDDER"] = "fake"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db, _ = build_populated_db(tmp)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    from embedder import backfill as bf
                    bf.main(["--db", str(db)])
                self.assertIn("BACKFILL", buf.getvalue())
                self.assertIn("processed=", buf.getvalue())
        finally:
            os.environ.pop("CLAUDE_EMBEDDER", None)


def _insert_private_row(db):
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "INSERT INTO observations (content_hash, session_id, "
            "timestamp, tool, is_private, searchable_text) VALUES "
            "('privhash1', 'sp', '2026-04-01T00:10:00Z', 'Secret', 1, "
            "'secret body')")
        con.commit()
    finally:
        con.close()


if __name__ == "__main__":
    unittest.main()

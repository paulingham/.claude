"""Slice 13a: WAL journal_mode + live_writer capture timeout=5.0."""
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))

import _support  # noqa: F401 — side-effect: paths
from _lib import schema  # noqa: E402


class WalModeApplied(unittest.TestCase):
    def test_fresh_db_reports_wal_journal_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            con = sqlite3.connect(str(db))
            try:
                mode = con.execute("PRAGMA journal_mode").fetchone()[0]
            finally:
                con.close()
            self.assertEqual(mode.lower(), "wal")


class CaptureTimeoutIsFiveSeconds(unittest.TestCase):
    def test_live_writer_uses_timeout_5s(self):
        src = (REPO_ROOT / "skills" / "reindex-memory" / "_lib"
               / "live_writer.py").read_text()
        self.assertRegex(src, r"timeout\s*=\s*5\.0")


if __name__ == "__main__":
    unittest.main()

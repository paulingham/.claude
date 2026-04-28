"""Tests for learning_gc_vacuum.vacuum_db."""
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

import learning_gc_vacuum  # noqa: E402


class VacuumDb(unittest.TestCase):
    def test_returns_true_on_real_sqlite_file(self):
        if shutil.which("sqlite3") is None:
            self.skipTest("sqlite3 CLI not available")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE t (id INTEGER)")
            conn.commit()
            conn.close()
            self.assertTrue(learning_gc_vacuum.vacuum_db(db))

    def test_returns_false_when_db_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(
                learning_gc_vacuum.vacuum_db(Path(tmp) / "absent.sqlite"))


if __name__ == "__main__":
    unittest.main()

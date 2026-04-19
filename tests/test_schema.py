"""Unit tests for _lib.schema.ensure drift semantics."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

import _support  # noqa: F401  — side-effect: adds skills/reindex-memory to sys.path
from _lib import schema  # noqa: E402


def _set_version(db, version):
    con = sqlite3.connect(str(db))
    con.execute("UPDATE schema_version SET version = ?", (version,))
    con.commit()
    con.close()


class EnsureReturnsFalseOnFreshDb(unittest.TestCase):
    def test_first_ensure_does_not_report_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            self.assertFalse(schema.ensure(db))


class EnsureReturnsFalseWhenVersionMatches(unittest.TestCase):
    def test_second_ensure_on_current_version_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            self.assertFalse(schema.ensure(db))


class EnsureReturnsTrueWhenVersionStale(unittest.TestCase):
    def test_rewound_version_triggers_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            _set_version(db, 0)
            self.assertTrue(schema.ensure(db))


if __name__ == "__main__":
    unittest.main()

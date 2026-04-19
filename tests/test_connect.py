"""Read-only SQLite connector: writes must raise, reads must succeed."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_populated_db  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import connect  # noqa: E402


class ReadOnlyConnection(unittest.TestCase):
    def test_write_raises_operational_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            con = connect.read_only(db)
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    con.execute("DELETE FROM observations")
            finally:
                con.close()


if __name__ == "__main__":
    unittest.main()

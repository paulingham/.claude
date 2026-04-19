"""Unit tests for _lib.ingest.ingest_all boundary behavior."""
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from _support import write_malformed_jsonl  # side-effect: adds sys.path
from _lib import ingest, schema  # noqa: E402


def _empty_db_and_learning(tmp):
    db = Path(tmp) / "memory.sqlite"
    learning = Path(tmp) / "learning"
    learning.mkdir()
    schema.ensure(db)
    return db, learning


class IngestAllOnEmptyDirReturnsZeros(unittest.TestCase):
    def test_no_files_produces_all_zero_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, learning = _empty_db_and_learning(tmp)
            summary = ingest.ingest_all(db, learning)
            self.assertEqual(summary.inserted, 0)
            self.assertEqual(summary.skipped, 0)
            self.assertEqual(summary.bad, 0)


class IngestAllOnAllBadFileCountsBadLines(unittest.TestCase):
    def test_bad_lines_increment_bad_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, learning = write_malformed_jsonl(
                tmp, "not json line 1\nalso not json\n")
            schema.ensure(db)
            with redirect_stderr(io.StringIO()):
                summary = ingest.ingest_all(db, learning)
            self.assertEqual(summary.inserted, 0)
            self.assertGreaterEqual(summary.bad, 2)


if __name__ == "__main__":
    unittest.main()

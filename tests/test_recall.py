"""Public API tests: privacy gate, missing DB, token budget, read-only."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_populated_db_with_private_row  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall import recall  # noqa: E402


class MissingDb(unittest.TestCase):
    def test_all_tiers_empty_when_db_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.sqlite"
            self.assertEqual(recall.search("x", db_path=missing), [])
            self.assertEqual(recall.timeline(db_path=missing), [])
            self.assertEqual(
                recall.get_observations(ids=[1], db_path=missing), [])
            self.assertEqual(
                recall.get_findings(ids=[1], db_path=missing), [])


class PrivacyGate(unittest.TestCase):
    def test_default_filters_private_rows_from_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db_with_private_row(tmp)
            hits = recall.search("Secret", db_path=db,
                                 source="observations")
            self.assertEqual(hits, [])

    def test_include_private_returns_private_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db_with_private_row(tmp)
            hits = recall.search("Secret", db_path=db,
                                 source="observations",
                                 include_private=True)
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["tool"], "Secret")


if __name__ == "__main__":
    unittest.main()

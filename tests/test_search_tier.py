"""Tier 1: search — bm25-ranked FTS5 hits, compact payload."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_populated_db  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import search_tier  # noqa: E402


class SearchObservations(unittest.TestCase):
    def test_returns_fts_ranked_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            hits = search_tier.search_observations(db, "Read")
            self.assertGreaterEqual(len(hits), 1)
            self.assertEqual(hits[0]["tool"], "Read")

    def test_hit_payload_under_200_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            hits = search_tier.search_observations(db, "Read")
            for hit in hits:
                blob = json.dumps(hit, separators=(",", ":"))
                self.assertLessEqual(len(blob.encode()), 200)


if __name__ == "__main__":
    unittest.main()

"""Tier 1: search — bm25-ranked FTS5 hits, compact payload."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_populated_db, insert_scratchpad_rows  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import search_tier  # noqa: E402


def _scratchpad_fixture():
    return [
        {"hash": "sp1", "task": "t1", "cat": "discovery", "role": "eng",
         "phase": "build", "ts": "2026-04-01T10:00:00Z",
         "body": "widget insight alpha", "priv": 0},
        {"hash": "sp2", "task": "t1", "cat": "warning", "role": "eng",
         "phase": "build", "ts": "2026-04-01T10:00:01Z",
         "body": "widget trap beta", "priv": 0},
    ]


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
                public = {k: v for k, v in hit.items()
                          if not k.startswith("_")}
                blob = json.dumps(public, separators=(",", ":"))
                self.assertLessEqual(len(blob.encode()), 200)


class SearchScratchpad(unittest.TestCase):
    def test_source_scratchpad_returns_scratchpad_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, _scratchpad_fixture())
            hits = search_tier.search_scratchpad(db, "widget")
            self.assertGreaterEqual(len(hits), 2)
            self.assertEqual(
                {h["source"] for h in hits}, {"scratchpad"})


class MalformedQuery(unittest.TestCase):
    def test_invalid_fts_syntax_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            hits = search_tier.search_observations(db, '" OR 1=1 --')
            self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()

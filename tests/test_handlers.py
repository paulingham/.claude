"""Tests for mcp_memory._lib.handlers — tool-call implementations."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mcp_support  # noqa: F401,E402
from _support import build_populated_db, insert_scratchpad_rows  # noqa: E402
from mcp_memory._lib import handlers  # noqa: E402
from recall import recall  # noqa: E402


class TestSearchMemoryHandler(unittest.TestCase):
    def test_returns_envelope_matching_recall_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            env = handlers.search_memory(
                {"query": "Read", "db_path": str(db)})
            self.assertEqual(env["tier"], "search")
            expected = recall.search("Read", source="both",
                                     limit=21, db_path=str(db))[:20]
            self.assertEqual(env["hits"], expected)
            self.assertFalse(env["truncated"])

    def test_missing_db_returns_empty_envelope(self):
        env = handlers.search_memory(
            {"query": "x", "db_path": "/tmp/nope.sqlite"})
        self.assertEqual(env["hits"], [])
        self.assertEqual(env["total"], 0)
        self.assertFalse(env["truncated"])


class TestSearchMemoryWhitelist(unittest.TestCase):
    def test_unknown_key_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            env = handlers.search_memory(
                {"query": "Read", "db_path": str(db),
                 "unknown_key": "smuggle"})
            self.assertEqual(env["tier"], "search")


class TestGetTimelineHandler(unittest.TestCase):
    def test_returns_envelope_ordered_by_timestamp_asc(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            env = handlers.get_timeline(
                {"source": "observations", "db_path": str(db)})
            self.assertEqual(env["tier"], "timeline")
            timestamps = [h["timestamp"] for h in env["hits"]]
            self.assertEqual(timestamps, sorted(timestamps))

    def test_both_source_includes_scratchpad_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, [{
                "hash": "ts1", "task": "t1", "cat": "pattern",
                "role": "eng", "phase": "build",
                "ts": "2026-04-01T10:00:00Z",
                "body": "timeline body", "priv": 0}])
            env = handlers.get_timeline(
                {"source": "both", "db_path": str(db)})
            sources = {h.get("source") for h in env["hits"]}
            self.assertIn("scratchpad", sources)


if __name__ == "__main__":
    unittest.main()

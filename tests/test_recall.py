"""Public API tests: privacy gate, missing DB, token budget, read-only."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (
    build_populated_db, build_populated_db_with_private_row, count_rows,
    insert_scratchpad_rows)  # noqa: E402

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


class PrivacyGateScratchpad(unittest.TestCase):
    def test_default_filters_private_findings_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, [{
                "hash": "psp1", "task": "t1", "cat": "warning",
                "role": "eng", "phase": "build",
                "ts": "2026-04-01T10:00:00Z",
                "body": "secret sauce", "priv": 1}])
            hits = recall.search("secret", db_path=db, source="scratchpad")
            self.assertEqual(hits, [])
            unlocked = recall.search("secret", db_path=db,
                                     source="scratchpad",
                                     include_private=True)
            self.assertEqual(len(unlocked), 1)


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


class ReadOnly(unittest.TestCase):
    def test_no_writes_after_full_exercise(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            before = _snapshot(db)
            for _ in range(5):
                recall.search("Read", db_path=db, source="observations")
                recall.timeline(db_path=db)
                recall.get_observations(ids=[1], db_path=db)
                recall.get_findings(ids=[1], db_path=db)
            self.assertEqual(_snapshot(db), before)


def _snapshot(db):
    return tuple(count_rows(db, t) for t in (
        "observations", "observations_fts",
        "scratchpad_findings", "embeddings"))


class SearchBoth(unittest.TestCase):
    def test_source_both_unions_and_tags_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, [{
                "hash": "sp1", "task": "t1", "cat": "pattern",
                "role": "eng", "phase": "build",
                "ts": "2026-04-01T10:00:00Z",
                "body": "Read widget alpha", "priv": 0}])
            hits = recall.search("Read", db_path=db, source="both")
            sources = {h["source"] for h in hits}
            self.assertIn("observations", sources)
            self.assertIn("scratchpad", sources)


class TokenBudget(unittest.TestCase):
    def test_progressive_disclosure_ten_x_reduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            _seed_widgets(db, 50)
            hits = recall.search("widget", db_path=db,
                                 source="observations", limit=20)
            full = recall.get_observations(
                ids=[h["id"] for h in hits[:3]], db_path=db)
            small = _bytes(hits + full)
            huge = _bytes(_dump_all(db))
            self.assertGreaterEqual(huge / max(small, 1), 10)


def _bytes(obj):
    return len(json.dumps(obj, separators=(",", ":")).encode())


def _seed_widgets(db, n):
    # Production searchable_text concatenates tool + file + outcome blobs
    # (outcomes carry captured output). 1KB per row is a realistic minimum.
    bulk = "widget data payload blob " * 40
    con = sqlite3.connect(str(db))
    try:
        for i in range(n):
            con.execute(
                "INSERT INTO observations (content_hash, session_id, "
                "timestamp, tool, file, searchable_text, is_private) "
                "VALUES (?, 'sw', ?, 'Read', '/widgets/w.py', ?, 0)",
                (f"widget{i}", f"2026-04-02T00:00:{i:02d}Z", bulk))
        con.commit()
    finally:
        con.close()


def _dump_all(db):
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(
            "SELECT * FROM observations").fetchall()]
    finally:
        con.close()


if __name__ == "__main__":
    unittest.main()

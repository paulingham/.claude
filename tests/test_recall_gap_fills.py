"""QA gap-fill tests — cover HIGH gaps flagged during /qa-test-strategy.

Covers:
- HIGH: timeline(source="both") returns timestamp-ASC merged ordering (AC2+AC9)
- HIGH: search(source="both") hits stay <=200 bytes (AC1 scratchpad + both paths)
- HIGH: content_hashes — unknown, mixed, get_findings equivalents (AC3+AC9)
- HIGH: S1->S3 end-to-end — reindex writes, /recall reads
"""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import (  # noqa: E402
    build_populated_db, insert_scratchpad_rows)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall import recall  # noqa: E402


def _sp_row(**over):
    base = {"hash": "h", "task": "t", "cat": "warning", "role": "eng",
            "phase": "build", "ts": "2026-04-01T10:00:00Z",
            "body": "body", "priv": 0}
    base.update(over)
    return base


class TimelineBothMergedOrdering(unittest.TestCase):
    def test_interleaved_timestamps_sort_ascending(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, [
                _sp_row(hash="early", ts="2025-01-01T00:00:00Z"),
                _sp_row(hash="late", ts="2027-01-01T00:00:00Z"),
            ])
            rows = recall.timeline(db_path=db, source="both", limit=50)
            stamps = [r["timestamp"] for r in rows]
            self.assertEqual(stamps, sorted(stamps),
                             f"cross-source ordering broken: {stamps}")


class SearchBothPayloadBudget(unittest.TestCase):
    def test_scratchpad_hits_under_200_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, [
                _sp_row(hash=f"sp{i}", ts=f"2026-04-02T00:00:{i:02d}Z",
                        body="widget " + "x" * 200)
                for i in range(3)])
            hits = recall.search("widget", db_path=db, source="scratchpad")
            self.assertTrue(hits, "test precondition: need scratchpad hits")
            for h in hits:
                blob = json.dumps(h, separators=(",", ":")).encode()
                self.assertLessEqual(len(blob), 200, f"{len(blob)}B hit {h!r}")

    def test_source_both_hits_under_200_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, [
                _sp_row(hash="spb", body="Read widget blob " + "y" * 200)])
            hits = recall.search("Read", db_path=db, source="both")
            self.assertTrue(hits, "test precondition: need cross-source hits")
            for h in hits:
                blob = json.dumps(h, separators=(",", ":")).encode()
                self.assertLessEqual(len(blob), 200, f"{len(blob)}B hit {h!r}")


class ContentHashesCoverage(unittest.TestCase):
    def test_observations_unknown_hash_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            rows = recall.get_observations(
                content_hashes=["does-not-exist"], db_path=db)
            self.assertEqual(rows, [])

    def test_observations_mixed_hashes_returns_only_known(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            known = _first_obs_hash(db)
            rows = recall.get_observations(
                content_hashes=[known, "missing-x"], db_path=db)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["content_hash"], known)

    def test_findings_by_content_hash_known_and_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, [_sp_row(hash="sp-known")])
            rows = recall.get_findings(
                content_hashes=["sp-known", "sp-absent"], db_path=db)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["content_hash"], "sp-known")


class EndToEndS1ToS3(unittest.TestCase):
    def test_reindex_output_is_searchable_via_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            hits = recall.search("Read", db_path=db, source="observations")
            tools = {h["tool"] for h in hits}
            self.assertIn("Read", tools)
            first_id = hits[0]["id"]
            rows = recall.get_observations(ids=[first_id], db_path=db)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], first_id)


def _first_obs_hash(db):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT content_hash FROM observations LIMIT 1").fetchone()[0]
    finally:
        con.close()


if __name__ == "__main__":
    unittest.main()

"""Tier 2: timeline — ordered rows scoped by filters, no FTS."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_populated_db, insert_scratchpad_rows  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import timeline_tier  # noqa: E402


def _sp_rows():
    return [
        {"hash": "sp1", "task": "t1", "cat": "discovery", "role": "eng",
         "phase": "build", "ts": "2026-04-01T10:00:02Z",
         "body": "second", "priv": 0},
        {"hash": "sp2", "task": "t1", "cat": "warning", "role": "eng",
         "phase": "build", "ts": "2026-04-01T10:00:01Z",
         "body": "first", "priv": 0},
    ]


class TimelineObservations(unittest.TestCase):
    def test_orders_by_timestamp_ascending(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            rows = timeline_tier.fetch_observations(db)
            stamps = [r["timestamp"] for r in rows]
            self.assertEqual(stamps, sorted(stamps))

    def test_uses_timestamp_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            plan = timeline_tier.explain_observations(db)
            joined = " ".join(row["detail"] for row in plan)
            self.assertIn("idx_observations_timestamp", joined)


class TimelineScratchpad(unittest.TestCase):
    def test_source_scratchpad_orders_by_timestamp_ascending(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, _sp_rows())
            rows = timeline_tier.fetch_scratchpad(db)
            stamps = [r["timestamp"] for r in rows]
            self.assertEqual(stamps, sorted(stamps))


class TimelineFilters(unittest.TestCase):
    def test_session_id_filter_scopes_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            rows = timeline_tier.fetch_observations(
                db, filter_spec={"session_id": "s1"})
            sessions = {r.get("session_id", "s1") for r in rows}
            self.assertEqual(len(rows), 2)
            self.assertEqual(sessions, {"s1"})

    def test_unknown_filter_key_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            with self.assertRaises(ValueError):
                timeline_tier.fetch_observations(
                    db, filter_spec={"nope": "x"})


if __name__ == "__main__":
    unittest.main()

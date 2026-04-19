"""Tier 2: timeline — ordered rows scoped by filters, no FTS."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_populated_db  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import timeline_tier  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()

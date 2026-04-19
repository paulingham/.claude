"""Tier 3: hydrate_tier — fetch full observation rows by id/content_hash."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _support import build_populated_db, insert_scratchpad_rows  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from recall._lib import hydrate_tier  # noqa: E402


def _sp_two():
    return [
        {"hash": "sp1", "task": "t1", "cat": "discovery", "role": "eng",
         "phase": "build", "ts": "2026-04-01T10:00:00Z",
         "body": "alpha", "priv": 0},
        {"hash": "sp2", "task": "t1", "cat": "warning", "role": "eng",
         "phase": "build", "ts": "2026-04-01T10:00:01Z",
         "body": "beta", "priv": 0},
    ]


class FetchByIds(unittest.TestCase):
    def test_returns_known_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            rows = hydrate_tier.fetch_by_ids(db, [1, 2])
            self.assertEqual({r["id"] for r in rows}, {1, 2})

    def test_omits_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            rows = hydrate_tier.fetch_by_ids(db, [1, 999])
            self.assertEqual([r["id"] for r in rows], [1])


class FetchFindingsByIds(unittest.TestCase):
    def test_known_ids_returned_unknown_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            insert_scratchpad_rows(db, _sp_two())
            rows = hydrate_tier.fetch_findings_by_ids(db, [1, 999])
            self.assertEqual([r["id"] for r in rows], [1])


if __name__ == "__main__":
    unittest.main()

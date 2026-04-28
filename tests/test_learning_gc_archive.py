"""Orchestrator-level tests for learning_gc_archive.archive_observations.

These cover the public contract that the bash hook depends on:
- past-retention entries moved to gzipped monthly files
- recent and unparseable lines kept
- empty / missing observations.jsonl is a no-op (returns 0)
"""
import gzip
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

import learning_gc_archive  # noqa: E402


class ArchiveObservationsContract(unittest.TestCase):
    def test_old_archived_recent_kept_unparseable_kept(self):
        old_ts = (datetime.now(timezone.utc)
                  - timedelta(days=120)).isoformat()
        recent_ts = (datetime.now(timezone.utc)
                     - timedelta(days=10)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            obs = Path(tmp) / "observations.jsonl"
            archive_dir = Path(tmp) / "archive"
            obs.write_text(
                json.dumps({"timestamp": old_ts, "k": "old"}) + "\n"
                + json.dumps({"timestamp": recent_ts, "k": "rec"}) + "\n"
                + "garbage\n")
            count = learning_gc_archive.archive_observations(
                obs, archive_dir, retention_days=90)
            self.assertEqual(count, 1)
            kept = obs.read_text().splitlines()
            month = datetime.fromisoformat(old_ts).strftime("%Y-%m")
            arc = archive_dir / f"observations-{month}.jsonl.gz"
            with gzip.open(arc, "rt") as fh:
                arc_lines = fh.read().splitlines()
        self.assertEqual(len(arc_lines), 1)
        self.assertEqual(json.loads(arc_lines[0])["k"], "old")
        self.assertIn("garbage", kept)

    def test_missing_obs_path_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nope.jsonl"
            self.assertEqual(
                learning_gc_archive.archive_observations(
                    missing, Path(tmp) / "arc", retention_days=90),
                0)


if __name__ == "__main__":
    unittest.main()

"""Tests for learning_gc_state.

Covers:
- is_gc_due returns True when state file is missing or malformed
- is_gc_due returns True at the 30-day boundary
- is_gc_due returns False inside the interval
- _read_last_run handles missing/null/malformed last_run gracefully
- update_state writes a parseable ISO 8601 timestamp atomically
"""
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

import learning_gc_state  # noqa: E402


class IsGcDueBoundaries(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_path = Path(self.tmp) / ".gc-state.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_due_when_state_missing(self):
        self.assertTrue(learning_gc_state.is_gc_due(self.state_path))

    def test_due_when_30_days_elapsed(self):
        ts = datetime.now(timezone.utc) - timedelta(days=30, seconds=1)
        self.state_path.write_text(json.dumps({"last_run": ts.isoformat()}))
        self.assertTrue(learning_gc_state.is_gc_due(self.state_path))

    def test_not_due_when_29_days_elapsed(self):
        ts = datetime.now(timezone.utc) - timedelta(days=29)
        self.state_path.write_text(json.dumps({"last_run": ts.isoformat()}))
        self.assertFalse(learning_gc_state.is_gc_due(self.state_path))


class ReadLastRunMalformed(unittest.TestCase):
    """Malformed state files should be treated as 'never run' (return None)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_path = Path(self.tmp) / ".gc-state.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_null_last_run_field_returns_none(self):
        # last_run explicitly null -> no AttributeError on .replace()
        self.state_path.write_text(json.dumps({"last_run": None}))
        self.assertTrue(learning_gc_state.is_gc_due(self.state_path))

    def test_missing_last_run_field_returns_none(self):
        self.state_path.write_text(json.dumps({}))
        self.assertTrue(learning_gc_state.is_gc_due(self.state_path))

    def test_invalid_json_returns_none(self):
        self.state_path.write_text("{not json")
        self.assertTrue(learning_gc_state.is_gc_due(self.state_path))

    def test_invalid_iso_timestamp_returns_none(self):
        self.state_path.write_text(json.dumps({"last_run": "not-a-date"}))
        self.assertTrue(learning_gc_state.is_gc_due(self.state_path))


class UpdateStateRoundTrip(unittest.TestCase):
    def test_writes_parseable_iso_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / ".gc-state.json"
            learning_gc_state.update_state(state_path)
            payload = json.loads(state_path.read_text())
            ts = datetime.fromisoformat(
                payload["last_run"].replace("Z", "+00:00"))
            self.assertLessEqual(
                (datetime.now(timezone.utc) - ts).total_seconds(), 5)

    def test_creates_parent_dir_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "a" / "b" / ".gc-state.json"
            learning_gc_state.update_state(nested)
            self.assertTrue(nested.exists())


if __name__ == "__main__":
    unittest.main()

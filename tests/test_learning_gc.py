"""Tests for the learning DB garbage-collection (GC) hook.

Covers:
  AC1 — is_gc_due triggers at the 30-day boundary
  AC2 — archive_observations moves only past-retention entries
  AC3 — vacuum_db runs without error
  AC4 — idempotent on repeated SessionStart same day
  AC5 — missing learning dir is a no-op
  AC6 — settings.json registers learning-gc.sh in SessionStart
"""
import gzip
import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

import learning_gc_state  # noqa: E402
import learning_gc_archive  # noqa: E402
import learning_gc_vacuum  # noqa: E402


class IsGcDueAt30DayBoundary(unittest.TestCase):
    """AC1 — GC triggers at 30-day boundary."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_path = Path(self.tmp) / ".gc-state.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_returns_true_when_state_missing(self):
        self.assertTrue(learning_gc_state.is_gc_due(self.state_path))

    def test_returns_true_when_last_run_30_days_ago(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=30, seconds=1))
        self.state_path.write_text(json.dumps(
            {"last_run": ts.isoformat()}))
        self.assertTrue(learning_gc_state.is_gc_due(self.state_path))

    def test_returns_false_when_last_run_29_days_ago(self):
        ts = datetime.now(timezone.utc) - timedelta(days=29)
        self.state_path.write_text(json.dumps(
            {"last_run": ts.isoformat()}))
        self.assertFalse(learning_gc_state.is_gc_due(self.state_path))


class ArchivesOnlyPastRetentionEntries(unittest.TestCase):
    """AC2 — archives only past-retention entries."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.obs = Path(self.tmp) / "observations.jsonl"
        self.archive_dir = Path(self.tmp) / "archive"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_old_entries_moved_recent_kept_unparseable_kept(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
        recent_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        self.obs.write_text(
            json.dumps({"timestamp": old_ts, "kind": "old"}) + "\n"
            + json.dumps({"timestamp": recent_ts, "kind": "recent"}) + "\n"
            + "not-json-no-timestamp\n")
        archived = learning_gc_archive.archive_observations(
            self.obs, self.archive_dir, retention_days=90)
        self.assertEqual(archived, 1)
        kept_lines = self.obs.read_text().splitlines()
        kept_kinds = []
        for line in kept_lines:
            try:
                kept_kinds.append(json.loads(line).get("kind"))
            except json.JSONDecodeError:
                kept_kinds.append("unparseable")
        self.assertNotIn("old", kept_kinds)
        self.assertIn("recent", kept_kinds)
        self.assertIn("unparseable", kept_kinds)
        month = datetime.fromisoformat(old_ts).strftime("%Y-%m")
        archive_file = self.archive_dir / f"observations-{month}.jsonl.gz"
        self.assertTrue(archive_file.exists())
        with gzip.open(archive_file, "rt") as fh:
            archived_lines = fh.read().splitlines()
        self.assertEqual(len(archived_lines), 1)
        self.assertEqual(json.loads(archived_lines[0]).get("kind"), "old")

    def test_no_old_lines_returns_zero(self):
        recent_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        self.obs.write_text(json.dumps({"timestamp": recent_ts}) + "\n")
        archived = learning_gc_archive.archive_observations(
            self.obs, self.archive_dir, retention_days=90)
        self.assertEqual(archived, 0)


class VacuumRunsWithoutError(unittest.TestCase):
    """AC3 — VACUUM runs without error."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = Path(self.tmp) / "memory.sqlite"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_returns_true_on_real_sqlite_file(self):
        if shutil.which("sqlite3") is None:
            self.skipTest("sqlite3 CLI not available")
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(self.db)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()
        self.assertTrue(learning_gc_vacuum.vacuum_db(self.db))

    def test_returns_false_when_db_missing(self):
        self.assertFalse(learning_gc_vacuum.vacuum_db(self.db))


class IdempotentSameDay(unittest.TestCase):
    """AC4 — idempotent on repeated SessionStart same day."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state_path = Path(self.tmp) / ".gc-state.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_second_call_same_day_returns_false(self):
        self.assertTrue(learning_gc_state.is_gc_due(self.state_path))
        learning_gc_state.update_state(self.state_path)
        self.assertFalse(learning_gc_state.is_gc_due(self.state_path))


class MissingLearningDirIsNoop(unittest.TestCase):
    """AC5 — missing obs path is a no-op."""

    def test_archive_observations_missing_path_returns_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist.jsonl"
            archive_dir = Path(tmp) / "archive"
            self.assertEqual(
                learning_gc_archive.archive_observations(
                    missing, archive_dir, retention_days=90),
                0)


class SettingsRegistersLearningGcHook(unittest.TestCase):
    """AC6 — settings.json registers learning-gc.sh in SessionStart."""

    def test_session_start_includes_learning_gc(self):
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        commands = []
        for group in settings["hooks"]["SessionStart"]:
            if "matcher" in group:
                continue
            for h in group.get("hooks", []):
                # v2.1.139 exec-form: command is the binary, args carries the path.
                cmd = h.get("command", "")
                args = h.get("args", []) or []
                commands.append(" ".join([cmd, *args]).strip())
        self.assertTrue(
            any("learning-gc.sh" in c for c in commands),
            f"learning-gc.sh not registered; got commands: {commands}")


if __name__ == "__main__":
    unittest.main()

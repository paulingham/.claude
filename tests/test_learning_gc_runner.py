"""Integration tests for hooks/_lib/learning_gc_runner.py.

The runner is invoked as a subprocess by hooks/learning-gc.sh with three
positional args: project_dir, retention_days, db_path. It must:

- skip silently when GC is not yet due
- archive past-retention observations on first run
- update .gc-state.json so the second run is a no-op
- swallow all exceptions and exit 0 (never block session start)
"""
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "hooks" / "_lib" / "learning_gc_runner.py"


def _run(project_dir: Path, retention: int = 90, db: Path = None):
    db = db or (project_dir / "missing.sqlite")
    return subprocess.run(
        [sys.executable, str(RUNNER), str(project_dir),
         str(retention), str(db)],
        capture_output=True, text=True)


class RunnerArchivesAndStamps(unittest.TestCase):
    def test_first_run_archives_old_lines_and_writes_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            old_ts = (datetime.now(timezone.utc)
                      - timedelta(days=120)).isoformat()
            (project / "observations.jsonl").write_text(
                json.dumps({"timestamp": old_ts}) + "\n")
            res = _run(project)
            self.assertEqual(res.returncode, 0)
            self.assertTrue((project / ".gc-state.json").exists())
            self.assertTrue((project / "archive").exists())

    def test_second_run_same_day_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".gc-state.json").write_text(json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat()}))
            recent_ts = (datetime.now(timezone.utc)
                         - timedelta(days=10)).isoformat()
            obs = project / "observations.jsonl"
            obs.write_text(json.dumps({"timestamp": recent_ts}) + "\n")
            res = _run(project)
            self.assertEqual(res.returncode, 0)
            self.assertFalse((project / "archive").exists())


class RunnerSwallowsErrors(unittest.TestCase):
    def test_missing_project_dir_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            absent = Path(tmp) / "does-not-exist"
            res = _run(absent)
            self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()

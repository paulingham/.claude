"""Tests for hooks/trace-cleanup.sh — session-dir mtime filter.

Covers:
  AC1 — Trace files older than 7 days are deleted (existing behaviour)
  AC2 — Fresh trace files in fresh session dirs survive
  AC3 — Stale session dirs (mtime > retention) are not enumerated for traces
        — i.e. when a session dir's mtime is past retention, its traces are
        unconditionally pruned without per-file stat
  AC4 — Empty session dirs are removed
  AC5 — Hook always exits 0
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "trace-cleanup.sh"


def _backdate(path: Path, days_old: float) -> None:
    when = time.time() - days_old * 86400
    os.utime(path, (when, when))


def _run(home: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CLAUDE_CONFIG_DIR"] = str(REPO_ROOT)
    env["CLAUDE_SESSION_ID"] = f"tc-{os.getpid()}"
    env["CLAUDE_HOOK_LOG_DIR"] = str(home / ".claude" / "metrics")
    return subprocess.run(
        ["bash", str(HOOK)],
        env=env,
        capture_output=True,
        text=True,
        input="",
    )


class _TraceCase(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="tc-home-"))
        self.metrics = self.home / ".claude" / "metrics"
        self.metrics.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _trace_file(self, session: str, fname: str, days_old: float) -> Path:
        sdir = self.metrics / session
        tdir = sdir / "trace"
        tdir.mkdir(parents=True, exist_ok=True)
        f = tdir / fname
        f.write_text("trace contents")
        if days_old > 0:
            _backdate(f, days_old)
            _backdate(tdir, days_old)
            _backdate(sdir, days_old)
        return f


class OldTracesPrunedFreshKept(_TraceCase):
    """AC1+AC2 — Old traces deleted, fresh ones kept."""

    def test_old_trace_deleted(self):
        old = self._trace_file("sess-a", "old.txt", days_old=10)
        fresh = self._trace_file("sess-b", "fresh.txt", days_old=0)
        result = _run(self.home)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())


class StaleSessionDirsNotEnumerated(_TraceCase):
    """AC3 — Stale session dirs handled without per-file stat.

    The intent is a perf optimisation: when the session dir mtime is past
    7 days, we know all traces inside are too. We don't need to stat each
    file individually. Verify the outcome (all traces gone) — the perf
    properties are an internal optimisation detail.
    """

    def test_stale_session_traces_pruned(self):
        for i in range(20):
            self._trace_file("ancient-sess", f"f{i}.txt", days_old=30)
        result = _run(self.home)
        self.assertEqual(result.returncode, 0)
        # All ancient traces should be gone
        ancient_trace_dir = self.metrics / "ancient-sess" / "trace"
        if ancient_trace_dir.exists():
            self.assertEqual(list(ancient_trace_dir.iterdir()), [],
                             "ancient session traces should all be pruned")


class EmptyDirsRemoved(_TraceCase):
    """AC4 — Empty session dirs removed."""

    def test_empty_session_dir_removed(self):
        empty = self.metrics / "empty-sess"
        empty.mkdir()
        result = _run(self.home)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(empty.exists(),
                         "empty session dir should be removed")


class AlwaysExitsZero(_TraceCase):
    """AC5 — Hook always exits 0."""

    def test_missing_metrics_dir(self):
        shutil.rmtree(self.metrics)
        result = _run(self.home)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()

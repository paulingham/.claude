"""Tests for scripts/hook-summary.sh --hours mtime filter.

Covers:
  AC1 — When --hours is set, files outside the window are not opened (perf path)
  AC2 — Behaviour identical when --hours is unset (no perf change)
  AC3 — Perf bound: 1000 stale dirs + 1 fresh dir completes in well under
        2 seconds with --hours 1
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "hook-summary.sh"


def _make_session(metrics_dir: Path, name: str, days_old: float,
                  hook_name: str = "x") -> Path:
    d = metrics_dir / name
    d.mkdir(parents=True)
    jsonl = d / "hooks.jsonl"
    fresh_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    jsonl.write_text(
        f'{{"timestamp":"{fresh_ts}","hook_name":"{hook_name}",'
        f'"trigger":"PreToolUse:Bash","duration_ms":1,"exit_code":0,'
        f'"session_id":"{name}"}}\n')
    if days_old > 0:
        when = time.time() - days_old * 86400
        os.utime(jsonl, (when, when))
        os.utime(d, (when, when))
    return d


def _run(metrics_dir: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_HOOK_LOG_DIR"] = str(metrics_dir)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env=env,
        capture_output=True,
        text=True,
    )


class HoursFilterSkipsStaleSessions(unittest.TestCase):
    """AC1 — --hours filter skips stale session dirs at the dir level."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hsh-"))
        self.metrics = self.tmp / "metrics"
        self.metrics.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stale_session_does_not_appear_in_output(self):
        # Stale dir is 10 days old; with --hours 24 the dir-mtime filter
        # must skip it. Using --hours 24 (rather than --hours 1) avoids
        # spurious failures from any timezone skew in record-timestamp
        # parsing — the filter under test is dir-level mtime.
        _make_session(self.metrics, "fresh-sess", days_old=0,
                      hook_name="fresh-hook")
        _make_session(self.metrics, "stale-sess", days_old=10,
                      hook_name="stale-hook")
        result = _run(self.metrics, "--hours", "24")
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("fresh-hook", result.stdout)
        self.assertNotIn("stale-hook", result.stdout)

    def test_unset_hours_includes_all(self):
        _make_session(self.metrics, "fresh-sess", days_old=0,
                      hook_name="fresh-hook")
        _make_session(self.metrics, "stale-sess", days_old=10,
                      hook_name="stale-hook")
        result = _run(self.metrics)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("fresh-hook", result.stdout)
        self.assertIn("stale-hook", result.stdout)


class HoursFilterPerfBound(unittest.TestCase):
    """AC3 — 1000 stale + 1 fresh dir completes in well under 2s with --hours 24.

    The perf goal is that the script does not OPEN stale files when --hours
    is set. We use --hours 24 (rather than --hours 1) so the test is robust
    to any TZ-related skew in record-level timestamp handling — the dir-level
    mtime filter is what's under test here, and stale dirs are 10 days old.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hsh-perf-"))
        self.metrics = self.tmp / "metrics"
        self.metrics.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_thousand_stale_one_fresh_under_two_seconds(self):
        # 1000 stale dirs (mtime 10 days ago) — must be skipped without opening.
        for i in range(1000):
            _make_session(self.metrics, f"stale-{i:04d}", days_old=10,
                          hook_name="stale-hook")
        # One fresh dir whose hooks.jsonl will be parsed.
        _make_session(self.metrics, "fresh-sess", days_old=0,
                      hook_name="fresh-hook")
        start = time.time()
        result = _run(self.metrics, "--hours", "24")
        elapsed = time.time() - start
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("fresh-hook", result.stdout)
        self.assertNotIn("stale-hook", result.stdout)
        self.assertLess(elapsed, 2.0,
                        f"--hours filter must skip stale dirs without opening; "
                        f"elapsed={elapsed:.2f}s")


if __name__ == "__main__":
    unittest.main()

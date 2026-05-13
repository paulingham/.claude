"""Tests for hooks/metrics-gc.sh — the metrics directory garbage collector.

Covers:
  AC1 — Test fixture dirs (test-*, rg-*, bats-*) are pruned unconditionally
  AC2 — local-* dirs older than retention are pruned, fresh ones survive
  AC3 — Stale subagent-runtimes/*.start files are pruned
  AC4 — Sentinel rate-limits subsequent runs within the interval
  AC5 — CLAUDE_DISABLE_METRICS_GC=1 fast-exits without side effects
  AC6 — settings.json registers metrics-gc.sh in SessionStart between
        learning-gc.sh and hook-self-test.sh
  AC7 — Hook always exits 0 (never blocks SessionStart)
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from tests._helpers.settings_hook import effective_command_line

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "metrics-gc.sh"


def _run_hook(home: Path, env_overrides: dict) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    # Point CLAUDE_CONFIG_DIR at the real harness so the hook's log.sh
    # source resolves; the hook still scans the test's metrics dir
    # (CLAUDE_HOOK_LOG_DIR), keeping the test isolated from real metrics.
    env["CLAUDE_CONFIG_DIR"] = str(REPO_ROOT)
    env["CLAUDE_SESSION_ID"] = f"test-mgc-{os.getpid()}"
    env["CLAUDE_HOOK_LOG_DIR"] = str(home / ".claude" / "metrics")
    env.pop("CLAUDE_DISABLE_METRICS_GC", None)
    env.pop("CLAUDE_METRICS_GC_INTERVAL_HOURS", None)
    env.pop("CLAUDE_METRICS_RETENTION_DAYS", None)
    env.pop("CLAUDE_SUBAGENT_MAX_RUNTIME", None)
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(HOOK)],
        env=env,
        capture_output=True,
        text=True,
        input="",
    )


def _backdate(path: Path, days_old: float) -> None:
    """Set mtime to N days in the past."""
    when = time.time() - days_old * 86400
    os.utime(path, (when, when))


class _MgcCase(unittest.TestCase):
    """Base setup for metrics-gc tests."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="mgc-home-"))
        self.metrics = self.home / ".claude" / "metrics"
        self.metrics.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def _make_session_dir(self, name: str, days_old: float = 0) -> Path:
        d = self.metrics / name
        d.mkdir()
        # Add a small file inside so the dir is realistic.
        (d / "hooks.jsonl").write_text('{"hook_name":"x"}\n')
        if days_old > 0:
            _backdate(d / "hooks.jsonl", days_old)
            _backdate(d, days_old)
        return d


class TestFixtureDirsPrunedUnconditionally(_MgcCase):
    """AC1 — test-*, rg-*, bats-* directories are pruned regardless of mtime."""

    def test_test_prefix_dirs_pruned_even_when_fresh(self):
        for name in ("test-abc", "test-cap-x", "test-fm-y",
                     "test-valid-z", "rg-foo", "bats-bar"):
            self._make_session_dir(name, days_old=0)
        result = _run_hook(self.home, {})
        self.assertEqual(result.returncode, 0,
                         msg=f"hook must exit 0; stderr: {result.stderr}")
        for name in ("test-abc", "test-cap-x", "test-fm-y",
                     "test-valid-z", "rg-foo", "bats-bar"):
            self.assertFalse((self.metrics / name).exists(),
                             f"{name} should have been pruned")


class LocalDirsAgedOutPruned(_MgcCase):
    """AC2 — local-* dirs past retention are pruned; fresh ones survive."""

    def test_old_local_dir_pruned_fresh_survives(self):
        self._make_session_dir("local-OLD", days_old=10)
        self._make_session_dir("local-NEW", days_old=1)
        result = _run_hook(self.home, {"CLAUDE_METRICS_RETENTION_DAYS": "7"})
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.metrics / "local-OLD").exists(),
                         "local-OLD older than 7 days should be pruned")
        self.assertTrue((self.metrics / "local-NEW").exists(),
                        "local-NEW within retention should survive")

    def test_default_retention_seven_days(self):
        # 8-day-old local-* should be pruned with default retention of 7 days
        self._make_session_dir("local-EIGHT", days_old=8)
        self._make_session_dir("local-ONE", days_old=1)
        result = _run_hook(self.home, {})
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.metrics / "local-EIGHT").exists())
        self.assertTrue((self.metrics / "local-ONE").exists())


class StaleStartFilesPruned(_MgcCase):
    """AC3 — Stale subagent-runtimes/*.start files are pruned, fresh ones kept."""

    def test_old_start_pruned_fresh_kept(self):
        session = self._make_session_dir("local-FRESH", days_old=0)
        runtimes = session / "subagent-runtimes"
        runtimes.mkdir()
        old_start = runtimes / "old.start"
        fresh_start = runtimes / "fresh.start"
        old_start.write_text("0:agent:foo")
        fresh_start.write_text("0:agent:bar")
        # Backdate old.start by more than CLAUDE_SUBAGENT_MAX_RUNTIME (1800s)
        old_time = time.time() - 3600
        os.utime(old_start, (old_time, old_time))
        # Bring session dir mtime back to recent so it's not pruned for being old.
        os.utime(session, (time.time(), time.time()))

        result = _run_hook(self.home, {})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertFalse(old_start.exists(),
                         "stale .start older than max-runtime should be pruned")
        self.assertTrue(fresh_start.exists(),
                        "fresh .start should survive")


class SentinelRateLimitsSubsequentRuns(_MgcCase):
    """AC4 — Sentinel suppresses runs within the configured interval."""

    def test_second_run_within_interval_no_op(self):
        # Create old test fixture so first run has work to do
        self._make_session_dir("test-first", days_old=0)
        first = _run_hook(self.home, {})
        self.assertEqual(first.returncode, 0)
        self.assertFalse((self.metrics / "test-first").exists())

        # Sentinel must exist now.
        sentinel = self.metrics / ".gc-state.json"
        self.assertTrue(sentinel.exists(),
                        "sentinel must be written after a successful run")
        sentinel_mtime_before = sentinel.stat().st_mtime

        # Create another fixture; second run within 24h should be a no-op.
        self._make_session_dir("test-second", days_old=0)
        second = _run_hook(self.home,
                           {"CLAUDE_METRICS_GC_INTERVAL_HOURS": "24"})
        self.assertEqual(second.returncode, 0)
        self.assertTrue((self.metrics / "test-second").exists(),
                        "rate-limited run must not delete fixture")
        self.assertEqual(sentinel.stat().st_mtime, sentinel_mtime_before,
                         "sentinel must not be rewritten when rate-limited")

    def test_zero_interval_always_runs(self):
        self._make_session_dir("test-a", days_old=0)
        first = _run_hook(self.home, {"CLAUDE_METRICS_GC_INTERVAL_HOURS": "0"})
        self.assertEqual(first.returncode, 0)
        self.assertFalse((self.metrics / "test-a").exists())
        self._make_session_dir("test-b", days_old=0)
        second = _run_hook(self.home, {"CLAUDE_METRICS_GC_INTERVAL_HOURS": "0"})
        self.assertEqual(second.returncode, 0)
        self.assertFalse((self.metrics / "test-b").exists())


class EscapeHatchDisablesGc(_MgcCase):
    """AC5 — CLAUDE_DISABLE_METRICS_GC=1 fast-exits with no side effects."""

    def test_disabled_does_nothing(self):
        self._make_session_dir("test-keep", days_old=0)
        result = _run_hook(self.home, {"CLAUDE_DISABLE_METRICS_GC": "1"})
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.metrics / "test-keep").exists(),
                        "disabled hook must not delete anything")
        self.assertFalse((self.metrics / ".gc-state.json").exists(),
                         "disabled hook must not write sentinel")


class SettingsRegistersMetricsGc(unittest.TestCase):
    """AC6 — settings.json registers metrics-gc.sh in SessionStart."""

    def test_session_start_includes_metrics_gc_between_learning_and_self_test(self):
        settings = json.loads((REPO_ROOT / "settings.json").read_text())
        commands = []
        for group in settings["hooks"]["SessionStart"]:
            if "matcher" in group:
                continue
            for h in group.get("hooks", []):
                effective = effective_command_line(h)
                if effective:
                    commands.append(effective)

        def index_of(needle: str) -> int:
            for i, c in enumerate(commands):
                if needle in c:
                    return i
            return -1

        learning_idx = index_of("learning-gc.sh")
        metrics_idx = index_of("metrics-gc.sh")
        self_test_idx = index_of("hook-self-test.sh")
        self.assertGreaterEqual(metrics_idx, 0,
                                "metrics-gc.sh must be registered")
        self.assertGreater(learning_idx, -1, "learning-gc.sh must be present")
        self.assertGreater(self_test_idx, -1, "hook-self-test.sh must be present")
        self.assertGreater(metrics_idx, learning_idx,
                           "metrics-gc.sh must come after learning-gc.sh")
        self.assertLess(metrics_idx, self_test_idx,
                        "metrics-gc.sh must come before hook-self-test.sh")


class HookExitsZeroOnUnexpectedConditions(_MgcCase):
    """AC7 — Hook never blocks SessionStart (always exits 0)."""

    def test_missing_metrics_dir_exits_zero(self):
        shutil.rmtree(self.metrics)
        result = _run_hook(self.home, {})
        self.assertEqual(result.returncode, 0,
                         msg=f"missing metrics dir must not crash: {result.stderr}")

    def test_empty_metrics_dir_exits_zero(self):
        result = _run_hook(self.home, {})
        self.assertEqual(result.returncode, 0)

    def test_sentinel_uses_python_json_format(self):
        """Sentinel is JSON with last_run epoch seconds (per spec)."""
        self._make_session_dir("test-x", days_old=0)
        result = _run_hook(self.home, {})
        self.assertEqual(result.returncode, 0)
        sentinel = self.metrics / ".gc-state.json"
        self.assertTrue(sentinel.exists())
        data = json.loads(sentinel.read_text())
        self.assertIn("last_run", data)
        self.assertIsInstance(data["last_run"], (int, float))
        self.assertAlmostEqual(data["last_run"], time.time(), delta=30)


if __name__ == "__main__":
    unittest.main()

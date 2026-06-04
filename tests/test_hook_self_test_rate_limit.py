"""Tests for the hook-self-test rate-limit gate.

Covers:
  AC1 — Fresh sentinel (<24h) suppresses execution; no hook-health.jsonl is written
  AC2 — Stale sentinel (>=24h) allows execution; hook-health.jsonl is written
  AC3 — Missing sentinel allows execution
  AC4 — Sentinel is written even when some hooks failed (don't loop-retry)
  AC5 — CLAUDE_DISABLE_HOOK_SELF_TEST=1 fast-exits regardless of sentinel
  AC6 — Custom interval honoured via CLAUDE_HOOK_SELF_TEST_INTERVAL_HOURS
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "hook-self-test.sh"


def _run_hook(home: Path, env_overrides: dict, config_dir: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["HOME"] = str(home)
    # CLAUDE_PLUGIN_DATA must match HOME/.claude so HARNESS_DATA resolves to
    # the same dir as the sentinel path assertion (home/.claude).
    env["CLAUDE_PLUGIN_DATA"] = str(home / ".claude")
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)
    env["CLAUDE_SESSION_ID"] = f"hst-{os.getpid()}"
    env["CLAUDE_HOOK_LOG_DIR"] = str(home / ".claude" / "metrics")
    env.pop("CLAUDE_DISABLE_HOOK_SELF_TEST", None)
    env.pop("CLAUDE_HOOK_SELF_TEST_INTERVAL_HOURS", None)
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(HOOK)],
        env=env,
        capture_output=True,
        text=True,
        input="",
    )


class _SelfTestCase(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="hst-home-"))
        self.config = self.home / ".claude-config"
        (self.config / "hooks" / "_lib").mkdir(parents=True)
        # Seed a no-op log lib so the hook's log lib source resolves.
        (self.config / "hooks" / "_lib" / "log.sh").write_text(
            "_log_hook_start() { :; }\n"
            "_log_hook_trigger() { :; }\n"
            "log_hook_event() { :; }\n"
        )
        # Seed a single trivial hook so the registration loop has something to iterate.
        dummy = self.config / "hooks" / "dummy-safe.sh"
        dummy.write_text("#!/usr/bin/env bash\nexit 0\n")
        os.chmod(dummy, 0o755)

        self.health_jsonl = (
            self.home / ".claude" / "metrics" / f"hst-{os.getpid()}"
            / "hook-health.jsonl")

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    @property
    def sentinel(self) -> Path:
        return self.home / ".claude" / ".hook-self-test-state.json"

    def _write_sentinel(self, age_seconds: int) -> None:
        self.sentinel.parent.mkdir(parents=True, exist_ok=True)
        self.sentinel.write_text(json.dumps(
            {"last_run": int(time.time()) - age_seconds}))


class FreshSentinelSuppresses(_SelfTestCase):
    """AC1 — Fresh sentinel (<24h) → fast-exit, no hook-health.jsonl produced."""

    def test_fresh_sentinel_blocks_run(self):
        self._write_sentinel(age_seconds=60)  # 1 minute ago
        result = _run_hook(self.home, {}, self.config)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.health_jsonl.exists(),
                         "hook-health.jsonl must not be written when rate-limited")


class StaleSentinelAllowsRun(_SelfTestCase):
    """AC2 — Sentinel >=24h old → run normally."""

    def test_stale_sentinel_runs(self):
        self._write_sentinel(age_seconds=25 * 3600)  # 25 hours ago
        result = _run_hook(self.home, {}, self.config)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self.health_jsonl.exists(),
                        "hook-health.jsonl must be written when allowed to run")


class MissingSentinelAllowsRun(_SelfTestCase):
    """AC3 — No sentinel → run normally and create one."""

    def test_no_sentinel_runs_and_writes_sentinel(self):
        self.assertFalse(self.sentinel.exists())
        result = _run_hook(self.home, {}, self.config)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self.health_jsonl.exists())
        self.assertTrue(self.sentinel.exists(),
                        "sentinel must be written after a successful run")


class SentinelWrittenEvenOnPartialFailure(_SelfTestCase):
    """AC4 — Sentinel still updated when a hook is broken, to avoid loop-retry."""

    def test_broken_hook_does_not_block_sentinel_update(self):
        broken = self.config / "hooks" / "dummy-broken.sh"
        broken.write_text("#!/usr/bin/env bash\nsyntax error here\n")
        os.chmod(broken, 0o755)
        result = _run_hook(self.home, {}, self.config)
        self.assertEqual(result.returncode, 0)
        # Sentinel must be written even though one hook had a syntax error.
        self.assertTrue(self.sentinel.exists())


class EscapeHatchSuppressesRun(_SelfTestCase):
    """AC5 — CLAUDE_DISABLE_HOOK_SELF_TEST=1 fast-exits with no work."""

    def test_disabled_no_op(self):
        result = _run_hook(self.home, {"CLAUDE_DISABLE_HOOK_SELF_TEST": "1"},
                           self.config)
        self.assertEqual(result.returncode, 0)
        self.assertFalse(self.health_jsonl.exists())
        self.assertFalse(self.sentinel.exists(),
                         "disabled hook must not write sentinel")


class CustomIntervalHonored(_SelfTestCase):
    """AC6 — CLAUDE_HOOK_SELF_TEST_INTERVAL_HOURS overrides the default."""

    def test_one_hour_interval(self):
        # Sentinel 90 minutes old; interval=1h → should re-run.
        self._write_sentinel(age_seconds=90 * 60)
        result = _run_hook(self.home,
                           {"CLAUDE_HOOK_SELF_TEST_INTERVAL_HOURS": "1"},
                           self.config)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self.health_jsonl.exists())


if __name__ == "__main__":
    unittest.main()

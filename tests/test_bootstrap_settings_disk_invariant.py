"""Regression guard: bootstrap tests must not mutate settings.json on disk."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_SETTINGS = Path.home() / ".claude" / "settings.json"
TF_MUTATED = "tempfile settings.json mutated by test subprocess"
REAL_MUTATED = "real ~/.claude/settings.json mutated by test subprocess"


def _child_env(tf_path: Path) -> dict:
    return {**os.environ, "CLAUDE_SETTINGS_PATH": str(tf_path),
            "PYTHONPATH": f"{REPO_ROOT}:{REPO_ROOT}/skills"}


def _run_bootstrap_suite(env: dict) -> None:
    subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_bootstrap",
         "tests.test_seed_user_settings"],
        env=env, cwd=str(REPO_ROOT), check=True, timeout=60)


def _make_tempfile_settings() -> Path:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tf:
        tf.write('{"env": {}}')
        return Path(tf.name)


class BootstrapSuiteLeavesSettingsByteIdentical(unittest.TestCase):
    def test_subprocess_unittest_preserves_both_settings_files(self):
        real_before = REAL_SETTINGS.read_bytes() if REAL_SETTINGS.exists() else None
        tf_path = _make_tempfile_settings()
        try:
            self._exercise(tf_path, real_before)
        finally:
            tf_path.unlink(missing_ok=True)

    def _exercise(self, tf_path: Path, real_before):
        tf_before = tf_path.read_bytes()
        try:
            _run_bootstrap_suite(_child_env(tf_path))
        except subprocess.TimeoutExpired:
            self.fail("bootstrap subprocess timed out after 60s")
        self.assertEqual(tf_path.read_bytes(), tf_before, TF_MUTATED)
        if real_before is not None:
            self.assertEqual(REAL_SETTINGS.read_bytes(), real_before, REAL_MUTATED)

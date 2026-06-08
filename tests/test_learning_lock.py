"""Wave-2 B11.1 — flock-based lock coordination test for learning hooks.

Verifies:
  - The shared lock helper sources cleanly and exposes with_learning_lock
  - Lock path uses /tmp/claude-learning-{project-hash}.lock and sanitizes the hash
  - Two concurrent invocations serialize (second blocks until first releases)
  - CLAUDE_LEARNING_FLOCK_DISABLE=1 falls back to no-op (no lock acquired)
  - auto-learn-gate.sh and learning-gc.sh both source learning-flock.sh
"""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LIB = REPO_ROOT / "hooks" / "_lib" / "learning-flock.sh"
AUTO_LEARN_GATE = REPO_ROOT / "hooks" / "auto-learn-gate.sh"
LEARNING_GC = REPO_ROOT / "hooks" / "learning-gc.sh"


def _bash(snippet: str, env: dict = None) -> subprocess.CompletedProcess:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    return subprocess.run(["bash", "-c", snippet], capture_output=True,
                          text=True, env=full_env)


class LibraryContract(unittest.TestCase):
    """The lock helper sources cleanly and exposes the expected functions."""

    def test_sources_without_error(self):
        result = _bash(f"source {LIB} && type with_learning_lock _learning_lock_path")
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_lock_path_matches_pattern(self):
        result = _bash(f"source {LIB} && _learning_lock_path 'abc123'")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "/tmp/claude-learning-abc123.lock")

    def test_lock_path_sanitizes_hash(self):
        result = _bash(f"source {LIB} && _learning_lock_path '../../etc/passwd'")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "/tmp/claude-learning-....etcpasswd.lock")

    def test_lock_path_falls_back_to_local_when_empty(self):
        result = _bash(f"source {LIB} && _learning_lock_path ''")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "/tmp/claude-learning-local.lock")


class WrapperContract(unittest.TestCase):
    """Both real hooks source the shared lock helper."""

    def test_auto_learn_gate_sources_learning_flock(self):
        text = AUTO_LEARN_GATE.read_text()
        self.assertIn("learning-flock.sh", text)
        self.assertIn("with_learning_lock", text)

    def test_learning_gc_sources_learning_flock(self):
        text = LEARNING_GC.read_text()
        self.assertIn("learning-flock.sh", text)
        self.assertIn("with_learning_lock", text)


class LockSerialization(unittest.TestCase):
    """Two concurrent invocations on the same hash serialize."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    @unittest.skipUnless(
        shutil.which("flock"),
        "flock(1) not available (e.g. stock macOS) — with_learning_lock falls "
        "back to no-op single-process semantics, so cross-process "
        "serialization cannot be exercised here. Validated on Linux/CI.")
    def test_concurrent_with_same_hash_serializes(self):
        marker = self.tmp / "events"
        # Start a holder that takes the lock for ~1.5s and writes timestamps.
        holder = subprocess.Popen([
            "bash", "-c",
            f"source {LIB} && _hold() {{ printf 'A start %s\\n' \"$(date +%s%N)\" >> {marker}; "
            f"sleep 1.5; printf 'A end %s\\n' \"$(date +%s%N)\" >> {marker}; }}; "
            f"with_learning_lock 'test-serialize' -- _hold"
        ])
        time.sleep(0.2)
        # Second invocation should block on the same hash.
        result = subprocess.run([
            "bash", "-c",
            f"source {LIB} && _t() {{ printf 'B run %s\\n' \"$(date +%s%N)\" >> {marker}; }}; "
            f"with_learning_lock 'test-serialize' -- _t"
        ], capture_output=True, text=True, timeout=10)
        holder.wait(timeout=10)
        self.assertEqual(result.returncode, 0, msg=result.stderr)

        events = marker.read_text().splitlines()
        self.assertEqual(len(events), 3)
        a_start = int(events[0].split()[-1])
        a_end = int(events[1].split()[-1])
        b_run = int(events[2].split()[-1])
        self.assertGreater(b_run, a_end,
                           msg="B must run after A releases the lock")
        # Sanity: A ran for ~1.5s.
        self.assertGreater(a_end - a_start, 1_000_000_000)


class DisableEscapeHatch(unittest.TestCase):
    """CLAUDE_LEARNING_FLOCK_DISABLE=1 falls back to no-op (callable runs but no lock)."""

    def test_disable_falls_back_to_passthrough(self):
        result = _bash(
            f"source {LIB} && _t() {{ echo ran; }}; with_learning_lock 'disabled-test' -- _t",
            env={"CLAUDE_LEARNING_FLOCK_DISABLE": "1"})
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "ran")


if __name__ == "__main__":
    unittest.main()

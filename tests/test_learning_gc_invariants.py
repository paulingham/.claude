"""Cross-cutting invariants for the learning-GC system.

Closes QA-identified gaps:
  AC3 — vacuum_db returns False when sqlite3 CLI unavailable
  AC7 — runner stamps .gc-state.json BEFORE invoking vacuum_db
  AC8 — CLAUDE_DISABLE_LEARNING_GC=1 fast-exits the bash hook
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

import learning_gc_runner  # noqa: E402
import learning_gc_vacuum  # noqa: E402

HOOK = REPO_ROOT / "hooks" / "learning-gc.sh"


def _seed_old_observation(learn_dir: Path) -> None:
    learn_dir.mkdir(parents=True)
    old_ts = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    (learn_dir / "observations.jsonl").write_text(
        json.dumps({"timestamp": old_ts}) + "\n")


class VacuumFallsBackWhenCliMissing(unittest.TestCase):
    """AC3 — graceful fallback when sqlite3 CLI is not on PATH."""

    def test_returns_false_when_sqlite3_cli_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            db.write_bytes(b"\x00")
            with mock.patch.object(learning_gc_vacuum.shutil,
                                   "which", return_value=None):
                self.assertFalse(learning_gc_vacuum.vacuum_db(db))


class StateStampedBeforeVacuum(unittest.TestCase):
    """AC7 — even if vacuum_db raises, .gc-state.json must already exist."""

    def test_state_file_written_even_when_vacuum_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "observations.jsonl").write_text("")
            with mock.patch.object(
                    learning_gc_runner, "vacuum_db",
                    side_effect=RuntimeError("simulated VACUUM hang")):
                with self.assertRaises(RuntimeError):
                    learning_gc_runner._do_gc(
                        project, 90, project / "memory.sqlite")
            payload = json.loads((project / ".gc-state.json").read_text())
            datetime.fromisoformat(payload["last_run"].replace("Z", "+00:00"))


class DisableEscapeHatchFastExits(unittest.TestCase):
    """AC8 — CLAUDE_DISABLE_LEARNING_GC=1 short-circuits the bash hook."""

    def test_first_executable_line_checks_disable_var(self):
        # GP-19 migrated the inline `[[ "$CLAUDE_DISABLE_LEARNING_GC" == "1" ]] && exit 0`
        # to `check_bypass_gate "CLAUDE_DISABLE_LEARNING_GC" && exit 0`, preceded by a
        # `source .../check-bypass-gate.sh` line.  The assertion now verifies that the
        # delegate call (which carries the env-var name) appears early in the executable
        # lines — before any substantive GC work — rather than checking `executable[0]`
        # literally (which is now the source line for the helper).
        executable = [
            line for line in HOOK.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
            and not line.strip().startswith("set ")]
        # Find the index of the bypass-gate call and verify it is within the first
        # three executable lines (source helper, delegate call, next source).
        bypass_indices = [
            i for i, line in enumerate(executable)
            if 'check_bypass_gate "CLAUDE_DISABLE_LEARNING_GC"' in line
        ]
        self.assertTrue(
            bypass_indices,
            "No check_bypass_gate call for CLAUDE_DISABLE_LEARNING_GC found in hook",
        )
        self.assertLess(
            bypass_indices[0], 3,
            f"check_bypass_gate call is at executable line {bypass_indices[0]} "
            f"(expected within first 3); hook may have moved the bypass check too late",
        )

    def test_disable_flag_prevents_archive_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            override = "disable-hatch-hash"
            learn_dir = home / ".claude" / "learning" / override
            _seed_old_observation(learn_dir)
            env = os.environ.copy()
            env.update({"HOME": str(home),
                        "CLAUDE_DISABLE_LEARNING_GC": "1",
                        "CLAUDE_PROJECT_HASH": override})
            result = subprocess.run(["bash", str(HOOK)], env=env,
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0)
            self.assertFalse((learn_dir / "archive").exists())
            self.assertFalse((learn_dir / ".gc-state.json").exists())


if __name__ == "__main__":
    unittest.main()

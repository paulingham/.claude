"""Regression guard: embedder import namespace must be intact after any rename.

Subprocess-runs a Python one-liner under PYTHONPATH=skills to confirm the
top-level `embedder` package and its key submodules remain importable.
This test is expected to be GREEN before and after the rename (regression guard).
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = str(REPO_ROOT / "skills")

_IMPORT_PROBE = (
    "import embedder; "
    "from embedder.embedder import get_embedder; "
    "from embedder import status; "
    "print('ok')"
)


class EmbedderImportNamespaceIntact(unittest.TestCase):
    def test_embedder_importable_on_pythonpath_skills(self):
        """All key embedder imports must succeed with PYTHONPATH=skills."""
        env = os.environ.copy()
        env["PYTHONPATH"] = SKILLS_DIR
        result = subprocess.run(
            [sys.executable, "-c", _IMPORT_PROBE],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Import probe failed (rc={result.returncode}):\nstdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertIn(
            "ok",
            result.stdout,
            f"Expected 'ok' in stdout but got: {result.stdout!r}",
        )


if __name__ == "__main__":
    unittest.main()

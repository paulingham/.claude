"""Unit tests for embedder._lib.bootstrap_steps.

AC9 gap coverage: subprocess.TimeoutExpired must be caught inside each
step so run() never raises to the caller.
"""
import io
import subprocess as sp
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib import bootstrap_steps  # noqa: E402


class InstallOrtSurvivesTimeout(unittest.TestCase):
    """AC9: TimeoutExpired from brew must be caught, not propagated."""
    def test_brew_timeout_warns_and_returns_partial(self):
        timeout_exc = sp.TimeoutExpired(
            cmd=["brew", "install", "onnxruntime"], timeout=300)
        buf = io.StringIO()
        with patch("embedder._lib.bootstrap_steps.shutil.which",
                   return_value="/opt/homebrew/bin/brew"), \
             patch("embedder._lib.bootstrap_steps.subprocess.run",
                   side_effect=timeout_exc):
            with redirect_stdout(buf):
                code = bootstrap_steps.install_ort()
        self.assertEqual(code, 1)
        self.assertIn("WARN", buf.getvalue())
        self.assertIn("brew", buf.getvalue())


class DownloadModelSurvivesTimeout(unittest.TestCase):
    """AC9: TimeoutExpired from download script must be caught."""
    def test_download_timeout_warns_and_returns_partial(self):
        timeout_exc = sp.TimeoutExpired(
            cmd=["bash", "download-model.sh"], timeout=600)
        buf = io.StringIO()
        with patch("embedder._lib.bootstrap_steps.subprocess.run",
                   side_effect=timeout_exc):
            with redirect_stdout(buf):
                code = bootstrap_steps.download_model()
        self.assertEqual(code, 1)
        self.assertIn("WARN", buf.getvalue())
        self.assertIn("download", buf.getvalue())


if __name__ == "__main__":
    unittest.main()

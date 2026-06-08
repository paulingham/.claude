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
        # Force the macOS (brew) install command so the timeout path is
        # exercised regardless of the host OS — otherwise install_cmd_for_os()
        # returns apt-get on a Linux CI runner and the test never reaches the
        # mocked subprocess.run.
        with patch("embedder._lib.bootstrap_steps.bootstrap_install.install_cmd_for_os",
                   return_value=(["brew", "install", "onnxruntime"], "brew")), \
             patch("embedder._lib.bootstrap_steps.shutil.which",
                   return_value="/opt/homebrew/bin/brew"), \
             patch("embedder._lib.bootstrap_steps.bootstrap_consent.grants",
                   return_value=True), \
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


class InstallOrtLinuxDispatchesAptGet(unittest.TestCase):
    """Slice 1: install_ort on Linux invokes apt-get, not brew."""
    def test_linux_shells_out_to_apt_get_install(self):
        import os
        from subprocess import CompletedProcess
        ok = CompletedProcess(args=[], returncode=0)
        with patch("embedder._lib.bootstrap_install.platform.system",
                   return_value="Linux"), \
             patch.dict(os.environ,
                        {"CLAUDE_BOOTSTRAP_CONSENT": "1"}, clear=False), \
             patch("embedder._lib.bootstrap_steps.shutil.which",
                   return_value="/usr/bin/apt-get"), \
             patch("embedder._lib.bootstrap_steps.subprocess.run",
                   return_value=ok) as sub:
            code = bootstrap_steps.install_ort()
        self.assertEqual(code, 0)
        cmd = sub.call_args.args[0]
        self.assertEqual(cmd[0], "sudo")
        self.assertIn("apt-get", cmd)
        self.assertIn("libonnxruntime-dev", cmd)


if __name__ == "__main__":
    unittest.main()

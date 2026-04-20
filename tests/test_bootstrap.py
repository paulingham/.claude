"""S9: embedder bootstrap — platform gate, brew install, download, patch.

run() returns 0 on healthy/bootstrapped, non-zero on skip/partial.
Graceful fallback on every failure path — never raises.
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib import bootstrap  # noqa: E402


class RunOnNonMacosSkips(unittest.TestCase):
    def test_linux_returns_skip_code_and_logs_skip_message(self):
        buf = io.StringIO()
        with patch("embedder._lib.bootstrap.platform.system",
                   return_value="Linux"):
            with redirect_stdout(buf):
                code = bootstrap.run()
        self.assertEqual(code, bootstrap.SKIP_NON_MACOS)
        self.assertIn("embedder bootstrap skipped (non-macOS)",
                      buf.getvalue())


class RunOnMacosHealthyIsNoop(unittest.TestCase):
    def test_healthy_system_returns_zero_without_side_effects(self):
        with patch("embedder._lib.bootstrap.platform.system",
                   return_value="Darwin"), \
             patch("embedder._lib.bootstrap._is_healthy",
                   return_value=True), \
             patch("embedder._lib.bootstrap_steps.subprocess.run") as sub, \
             patch("embedder._lib.settings_patch.patch") as sp:
            code = bootstrap.run()
        self.assertEqual(code, 0)
        sub.assert_not_called()
        sp.assert_not_called()


def _find_call(mock_run, needle):
    for c in mock_run.call_args_list:
        args = c.args[0] if c.args else []
        if any(needle in str(a) for a in args):
            return c
    return None


class RunWarnsWhenBrewAbsent(unittest.TestCase):
    def test_missing_brew_logs_warn_and_returns_partial(self):
        buf = io.StringIO()
        with patch("embedder._lib.bootstrap.platform.system",
                   return_value="Darwin"), \
             patch("embedder._lib.bootstrap._is_healthy",
                   return_value=False), \
             patch("embedder._lib.bootstrap._dylib_path",
                   return_value=Path("/nonexistent/libonnxruntime.dylib")), \
             patch("embedder._lib.bootstrap._model_path",
                   return_value=Path("/tmp/exists")), \
             patch("embedder._lib.bootstrap_steps.shutil.which",
                   return_value=None), \
             patch("embedder._lib.bootstrap_steps.subprocess.run") as sub:
            Path("/tmp/exists").touch()
            with redirect_stdout(buf):
                code = bootstrap.run()
        self.assertEqual(code, bootstrap.PARTIAL)
        self.assertIn("WARN", buf.getvalue())
        self.assertIn("brew", buf.getvalue())
        sub.assert_not_called()


class RunDownloadsModelWhenMissing(unittest.TestCase):
    def test_invokes_download_script_with_noninteractive_env(self):
        from subprocess import CompletedProcess
        ok = CompletedProcess(args=[], returncode=0)
        with patch("embedder._lib.bootstrap.platform.system",
                   return_value="Darwin"), \
             patch("embedder._lib.bootstrap._is_healthy",
                   return_value=False), \
             patch("embedder._lib.bootstrap._dylib_path",
                   return_value=Path("/tmp/exists")), \
             patch("embedder._lib.bootstrap._model_path",
                   return_value=Path("/nonexistent/model.onnx")), \
             patch("embedder._lib.bootstrap_steps.subprocess.run",
                   return_value=ok) as sub:
            Path("/tmp/exists").touch()
            bootstrap.run()
        call = _find_call(sub, "download-model.sh")
        self.assertIsNotNone(call)
        self.assertEqual(call.kwargs["env"].get("NONINTERACTIVE"), "1")


class RunWarnsWhenDownloadFails(unittest.TestCase):
    def test_download_script_nonzero_returns_partial(self):
        from subprocess import CompletedProcess
        failed = CompletedProcess(args=[], returncode=1)
        buf = io.StringIO()
        with patch("embedder._lib.bootstrap.platform.system",
                   return_value="Darwin"), \
             patch("embedder._lib.bootstrap._is_healthy",
                   return_value=False), \
             patch("embedder._lib.bootstrap._dylib_path",
                   return_value=Path("/tmp/exists")), \
             patch("embedder._lib.bootstrap._model_path",
                   return_value=Path("/nonexistent/model.onnx")), \
             patch("embedder._lib.bootstrap_steps.subprocess.run",
                   return_value=failed):
            Path("/tmp/exists").touch()
            with redirect_stdout(buf):
                code = bootstrap.run()
        self.assertEqual(code, bootstrap.PARTIAL)
        self.assertIn("model download failed", buf.getvalue())


class RunContinuesOnBrewFailure(unittest.TestCase):
    def test_nonzero_returncode_warns_and_returns_partial(self):
        from subprocess import CompletedProcess
        failed = CompletedProcess(args=[], returncode=1)
        buf = io.StringIO()
        with patch("embedder._lib.bootstrap.platform.system",
                   return_value="Darwin"), \
             patch("embedder._lib.bootstrap._is_healthy",
                   return_value=False), \
             patch("embedder._lib.bootstrap._dylib_path",
                   return_value=Path("/nonexistent/libonnxruntime.dylib")), \
             patch("embedder._lib.bootstrap._model_path",
                   return_value=Path("/tmp/exists")), \
             patch("embedder._lib.bootstrap_steps.shutil.which",
                   return_value="/opt/homebrew/bin/brew"), \
             patch("embedder._lib.bootstrap_steps.subprocess.run",
                   return_value=failed):
            Path("/tmp/exists").touch()
            with redirect_stdout(buf):
                code = bootstrap.run()
        self.assertEqual(code, bootstrap.PARTIAL)
        self.assertIn("brew install failed", buf.getvalue())


class RunInstallsOrtWhenDylibMissing(unittest.TestCase):
    def test_calls_brew_install_onnxruntime_with_timeout(self):
        from subprocess import CompletedProcess
        completed = CompletedProcess(args=[], returncode=0)
        with patch("embedder._lib.bootstrap.platform.system",
                   return_value="Darwin"), \
             patch("embedder._lib.bootstrap._is_healthy",
                   return_value=False), \
             patch("embedder._lib.bootstrap._dylib_path",
                   return_value=Path("/nonexistent/libonnxruntime.dylib")), \
             patch("embedder._lib.bootstrap._model_path",
                   return_value=Path("/nonexistent/model.onnx")), \
             patch("embedder._lib.bootstrap_steps.shutil.which",
                   return_value="/opt/homebrew/bin/brew"), \
             patch("embedder._lib.bootstrap_steps.subprocess.run",
                   return_value=completed) as sub:
            bootstrap.run()
        call = _find_call(sub, "brew")
        self.assertIsNotNone(call)
        self.assertEqual(list(call.args[0]),
                         ["brew", "install", "onnxruntime"])
        self.assertEqual(call.kwargs.get("timeout"), 300)


if __name__ == "__main__":
    unittest.main()

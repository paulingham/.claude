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


class RunPatchesSettingsWithResolvedDylib(unittest.TestCase):
    def test_writes_dylib_path_to_settings_env(self):
        import json
        import tempfile
        from subprocess import CompletedProcess
        ok = CompletedProcess(args=[], returncode=0)
        with tempfile.TemporaryDirectory() as d:
            settings = Path(d) / "settings.json"
            settings.write_text(json.dumps({"env": {}}))
            dylib = Path(d) / "libonnxruntime.dylib"
            dylib.touch()
            model = Path(d) / "model.onnx"
            model.touch()
            env_patch = {"CLAUDE_SETTINGS_PATH": str(settings)}
            with patch.dict(os.environ, env_patch, clear=False), \
                 patch("embedder._lib.bootstrap.platform.system",
                       return_value="Darwin"), \
                 patch("embedder._lib.bootstrap._is_healthy",
                       return_value=False), \
                 patch("embedder._lib.bootstrap._dylib_path",
                       return_value=dylib), \
                 patch("embedder._lib.bootstrap._model_path",
                       return_value=model), \
                 patch("embedder._lib.bootstrap_steps.subprocess.run",
                       return_value=ok):
                bootstrap.run()
            payload = json.loads(settings.read_text())
            self.assertEqual(
                payload["env"].get("ORT_DYLIB_PATH"), str(dylib))


class RunDoesNotClobberExistingSetting(unittest.TestCase):
    def test_existing_ort_dylib_path_preserved_byte_for_byte(self):
        import json
        import tempfile
        from subprocess import CompletedProcess
        ok = CompletedProcess(args=[], returncode=0)
        with tempfile.TemporaryDirectory() as d:
            settings = Path(d) / "settings.json"
            settings.write_text(
                json.dumps({"env": {"ORT_DYLIB_PATH": "/custom/path"}}))
            before = settings.read_bytes()
            dylib = Path(d) / "libonnxruntime.dylib"
            dylib.touch()
            model = Path(d) / "model.onnx"
            model.touch()
            env_patch = {"CLAUDE_SETTINGS_PATH": str(settings)}
            with patch.dict(os.environ, env_patch, clear=False), \
                 patch("embedder._lib.bootstrap.platform.system",
                       return_value="Darwin"), \
                 patch("embedder._lib.bootstrap._is_healthy",
                       return_value=False), \
                 patch("embedder._lib.bootstrap._dylib_path",
                       return_value=dylib), \
                 patch("embedder._lib.bootstrap._model_path",
                       return_value=model), \
                 patch("embedder._lib.bootstrap_steps.subprocess.run",
                       return_value=ok):
                bootstrap.run()
            self.assertEqual(settings.read_bytes(), before)


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


class RunAsModuleInvokesRun(unittest.TestCase):
    """S9 AC10: `python3 -m embedder._lib.bootstrap` invokes run()."""
    def test_module_main_exits_cleanly_without_raising(self):
        import subprocess
        # Force non-Darwin so we get deterministic skip output regardless
        # of the host's doctor state.
        result = subprocess.run(
            [sys.executable, "-c",
             "import platform; platform.system=lambda: 'Linux'; "
             "from embedder._lib import bootstrap as b; "
             "import sys; sys.exit(b.run())"],
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "skills")},
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, bootstrap.SKIP_NON_MACOS)
        self.assertIn("embedder bootstrap skipped", result.stdout)


if __name__ == "__main__":
    unittest.main()

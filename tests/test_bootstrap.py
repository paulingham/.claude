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


class RunOnLinuxBootstraps(unittest.TestCase):
    """Slice 1: Linux is no longer skipped — bootstrap runs with apt-get."""
    def test_linux_non_healthy_invokes_install_and_download_steps(self):
        from subprocess import CompletedProcess
        ok = CompletedProcess(args=[], returncode=0)
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            settings = Path(d) / "settings.json"
            settings.write_text('{"env": {}}')
            missing_dylib = Path(d) / "libonnxruntime.so"
            env_patch = {"CLAUDE_SETTINGS_PATH": str(settings)}
            with patch.dict(os.environ, env_patch, clear=False), \
                 patch("embedder._lib.bootstrap.platform.system",
                       return_value="Linux"), \
                 patch("embedder._lib.bootstrap._is_healthy",
                       return_value=False), \
                 patch("embedder._lib.bootstrap._dylib_path",
                       return_value=missing_dylib), \
                 patch("embedder._lib.bootstrap._model_path",
                       return_value=Path("/nonexistent/model.onnx")), \
                 patch("embedder._lib.bootstrap_install.platform.system",
                       return_value="Linux"), \
                 patch("embedder._lib.bootstrap_steps.shutil.which",
                       return_value="/usr/bin/apt-get"), \
                 patch("embedder._lib.bootstrap_steps.subprocess.run",
                       return_value=ok) as sub:
                code = bootstrap.run()
        self.assertNotEqual(code, 10)  # no longer SKIP_NON_MACOS
        commands = [list(c.args[0]) for c in sub.call_args_list]
        self.assertTrue(
            any("apt-get" in c for c in commands),
            f"expected apt-get dispatch on Linux, got {commands}")


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
        import tempfile
        from subprocess import CompletedProcess
        ok = CompletedProcess(args=[], returncode=0)
        with tempfile.TemporaryDirectory() as d:
            tmp_settings = Path(d) / "settings.json"
            tmp_settings.write_text('{"env": {}}')
            env_patch = {"CLAUDE_SETTINGS_PATH": str(tmp_settings)}
            with patch.dict(os.environ, env_patch, clear=False), \
                 patch("embedder._lib.bootstrap.platform.system",
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
        import tempfile
        from subprocess import CompletedProcess
        failed = CompletedProcess(args=[], returncode=1)
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            tmp_settings = Path(d) / "settings.json"
            tmp_settings.write_text('{"env": {}}')
            env_patch = {"CLAUDE_SETTINGS_PATH": str(tmp_settings)}
            with patch.dict(os.environ, env_patch, clear=False), \
                 patch("embedder._lib.bootstrap.platform.system",
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
    """S9 AC10: `python3 -m embedder._lib.bootstrap` invokes run().

    Slice 1: Linux is no longer skipped — only Windows is. Force Windows
    to produce deterministic skip output without needing a live ORT on
    the host.
    """
    def test_module_main_exits_cleanly_without_raising(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-c",
             "import platform; platform.system=lambda: 'Windows'; "
             "from embedder._lib import bootstrap as b; "
             "import sys; sys.exit(b.run())"],
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "skills")},
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, bootstrap.WIN_UNSUPPORTED)
        self.assertIn("embedder bootstrap skipped", result.stdout)


class RunIsIdempotent(unittest.TestCase):
    """AC8: two consecutive run() calls leave settings.json byte-identical."""
    def test_second_invocation_does_not_rewrite_settings(self):
        import json
        import tempfile
        import time
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
                bytes_after_first = settings.read_bytes()
                mtime_after_first = settings.stat().st_mtime_ns
                time.sleep(0.01)
                bootstrap.run()
                bytes_after_second = settings.read_bytes()
                mtime_after_second = settings.stat().st_mtime_ns
            self.assertEqual(bytes_after_second, bytes_after_first)
            self.assertEqual(mtime_after_second, mtime_after_first)


class RunPrintsSuccessLineAfterBootstrap(unittest.TestCase):
    """S9 polish: happy-path bootstrap emits ONE confirmation line.

    When brew install + model download + settings patch all succeed on
    macOS, the user sees confirmation — not just subprocess noise.
    """
    def test_bootstrap_happy_path_prints_confirmation(self):
        import json
        import tempfile
        from subprocess import CompletedProcess
        ok = CompletedProcess(args=[], returncode=0)
        buf = io.StringIO()
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
                with redirect_stdout(buf):
                    code = bootstrap.run()
        self.assertEqual(code, 0)
        self.assertIn(
            "embedder bootstrap complete (ORT_DYLIB_PATH written)",
            buf.getvalue())


class RunHealthyShortCircuitIsSilent(unittest.TestCase):
    """S9 polish: no-op healthy path prints nothing — zero noise."""
    def test_healthy_path_does_not_print_completion_line(self):
        buf = io.StringIO()
        with patch("embedder._lib.bootstrap.platform.system",
                   return_value="Darwin"), \
             patch("embedder._lib.bootstrap._is_healthy",
                   return_value=True):
            with redirect_stdout(buf):
                code = bootstrap.run()
        self.assertEqual(code, 0)
        self.assertNotIn("bootstrap complete", buf.getvalue())


class RunSurvivesSubprocessTimeout(unittest.TestCase):
    """AC9: TimeoutExpired mid-pipeline must not crash run()."""
    def test_timeout_returns_partial_not_exception(self):
        import subprocess as sp
        timeout_exc = sp.TimeoutExpired(
            cmd=["brew", "install", "onnxruntime"], timeout=300)
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
                   side_effect=timeout_exc):
            Path("/tmp/exists").touch()
            with redirect_stdout(buf):
                code = bootstrap.run()
        self.assertEqual(code, bootstrap.PARTIAL)
        self.assertIn("WARN", buf.getvalue())


if __name__ == "__main__":
    unittest.main()

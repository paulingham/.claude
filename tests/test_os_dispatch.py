"""M2: Three-way OS split — Darwin, Linux, else UnsupportedOSError.

The binary Linux-vs-default branches in bootstrap_install and
bootstrap_paths silently route unknown OSes (FreeBSD, Solaris, etc.)
to the macOS code path, producing misleading "brew not on PATH" errors.
Match detect-os.sh's explicit allowlist and raise on unknown.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib import bootstrap_install, bootstrap_paths  # noqa: E402
from embedder._lib.bootstrap_errors import UnsupportedOSError  # noqa: E402


class InstallCmdDarwinReturnsBrew(unittest.TestCase):
    def test_darwin_returns_brew_tuple(self):
        with patch("embedder._lib.bootstrap_install.platform.system",
                   return_value="Darwin"):
            cmd, tool = bootstrap_install.install_cmd_for_os()
        self.assertEqual(tool, "brew")


class InstallCmdLinuxReturnsApt(unittest.TestCase):
    def test_linux_returns_apt_tuple(self):
        with patch("embedder._lib.bootstrap_install.platform.system",
                   return_value="Linux"):
            cmd, tool = bootstrap_install.install_cmd_for_os()
        self.assertEqual(tool, "apt-get")


class InstallCmdUnknownRaises(unittest.TestCase):
    def test_freebsd_raises_unsupported_os(self):
        with patch("embedder._lib.bootstrap_install.platform.system",
                   return_value="FreeBSD"):
            with self.assertRaises(UnsupportedOSError) as ctx:
                bootstrap_install.install_cmd_for_os()
        self.assertIn("FreeBSD", str(ctx.exception))


class DylibPathUnknownRaises(unittest.TestCase):
    def test_solaris_raises_unsupported_os(self):
        import os
        env = {k: v for k, v in os.environ.items()
               if k != "ORT_DYLIB_PATH"}
        with patch.dict(os.environ, env, clear=True), \
             patch("embedder._lib.bootstrap_paths.platform.system",
                   return_value="SunOS"):
            with self.assertRaises(UnsupportedOSError) as ctx:
                bootstrap_paths.dylib_path()
        self.assertIn("SunOS", str(ctx.exception))


class UnsupportedOSErrorIsRuntimeError(unittest.TestCase):
    def test_subclass_of_runtime_error(self):
        self.assertTrue(issubclass(UnsupportedOSError, RuntimeError))


class RunHandlesUnsupportedOsGracefully(unittest.TestCase):
    """bootstrap.run() on FreeBSD logs a warning and returns PARTIAL —
    must not propagate UnsupportedOSError to the caller."""
    def test_freebsd_returns_partial_with_warning(self):
        import io
        from contextlib import redirect_stdout

        from embedder._lib import bootstrap
        buf = io.StringIO()
        with patch("embedder._lib.bootstrap.platform.system",
                   return_value="FreeBSD"), \
             patch("embedder._lib.bootstrap._is_healthy",
                   return_value=False):
            with redirect_stdout(buf):
                code = bootstrap.run()
        self.assertEqual(code, bootstrap.PARTIAL)
        self.assertIn("Unsupported OS", buf.getvalue())


if __name__ == "__main__":
    unittest.main()

"""Bootstrap path helpers — macOS + Linux probing via detect-ort.sh."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
_TESTS = str(REPO_ROOT / "tests")
for _p in (_SKILL, _TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from embedder._lib import bootstrap_paths  # noqa: E402
from env_sandbox import EnvSandbox  # noqa: E402


class DylibPathLinux(unittest.TestCase):
    def test_linux_returns_so_candidate_from_detect_ort(self):
        with tempfile.TemporaryDirectory() as d:
            fake_so = Path(d) / "libonnxruntime.so"
            fake_so.touch()
            env = {"ORT_DYLIB_PATH": str(fake_so)}
            with EnvSandbox(env), \
                 patch("embedder._lib.bootstrap_paths.platform.system",
                       return_value="Linux"):
                self.assertEqual(bootstrap_paths.dylib_path(), fake_so)


class DylibPathLinuxFallback(unittest.TestCase):
    def test_linux_without_env_returns_so_fallback_target(self):
        with EnvSandbox({"ORT_DYLIB_PATH": None}), \
             patch("embedder._lib.bootstrap_paths.platform.system",
                   return_value="Linux"):
            result = bootstrap_paths.dylib_path()
        self.assertTrue(str(result).endswith(".so"),
                        f"expected .so fallback on Linux, got {result}")


class DylibPathMacosFallback(unittest.TestCase):
    def test_macos_without_env_returns_dylib_fallback_target(self):
        with EnvSandbox({"ORT_DYLIB_PATH": None}), \
             patch("embedder._lib.bootstrap_paths.platform.system",
                   return_value="Darwin"):
            result = bootstrap_paths.dylib_path()
        self.assertTrue(str(result).endswith(".dylib"),
                        f"expected .dylib fallback on macOS, got {result}")


if __name__ == "__main__":
    unittest.main()

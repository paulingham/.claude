"""Integration test: ORT_DYLIB_PATH is the cross-module identifier used by
detect-ort.sh (shell), bootstrap_paths.py (Python), and download-model.sh.

Module-local unit tests are insufficient for cross-module contracts.
Learned pattern: every shared identifier must have a full-path integration
test that exercises it end-to-end. This test asserts:
  1. An override file written to disk is resolved identically by both the
     bash resolver and the Python resolver.
  2. settings.json no longer hardcodes the identifier.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(REPO_ROOT / "skills"), str(REPO_ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from env_sandbox import EnvSandbox  # noqa: E402

DETECT_ORT = REPO_ROOT / "scripts" / "_lib" / "detect-ort.sh"
SETTINGS_JSON = REPO_ROOT / "settings.json"


class OrtPathOverrideResolvesInBothLanguages(unittest.TestCase):
    def test_override_file_found_by_shell_and_python(self):
        if shutil.which("bash") is None:
            self.skipTest("bash unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp) / "libonnxruntime.so"
            override.touch()
            env = {"ORT_DYLIB_PATH": str(override),
                   "ORT_CANDIDATE_PATHS": ""}
            with EnvSandbox(env):
                shell_out = self._run_detect_ort()
                py_out = self._run_python_resolver()
            self.assertEqual(shell_out, str(override))
            self.assertEqual(py_out, str(override))

    def _run_detect_ort(self):
        import os
        result = subprocess.run(
            ["bash", "-c", f"source '{DETECT_ORT}'; detect_ort"],
            capture_output=True, text=True, check=True, env=os.environ.copy())
        return result.stdout.strip()

    def _run_python_resolver(self):
        from embedder._lib import bootstrap_paths
        return str(bootstrap_paths.dylib_path())


class SettingsJsonHasNoHardcodedOrtPath(unittest.TestCase):
    """Guard against regressions — the whole point of this slice."""
    def test_settings_json_does_not_hardcode_ort_dylib_path(self):
        import json
        data = json.loads(SETTINGS_JSON.read_text())
        self.assertNotIn("ORT_DYLIB_PATH", data.get("env", {}))


if __name__ == "__main__":
    unittest.main()

"""Integration test: ORT_DYLIB_PATH is the cross-module identifier used by
detect-ort.sh (shell), bootstrap_paths.py (Python), and download-model.sh.

Module-local unit tests are insufficient for cross-module contracts.
Learned pattern: every shared identifier must have a full-path integration
test that exercises it end-to-end. This test asserts:
  1. An override file written to disk is resolved identically by both the
     bash resolver and the Python resolver.
  2. settings.json no longer hardcodes the identifier.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))

DETECT_ORT = REPO_ROOT / "scripts" / "_lib" / "detect-ort.sh"
SETTINGS_JSON = REPO_ROOT / "settings.json"


class _EnvSandbox:
    """Save → modify → restore a set of env var keys. Learned pattern."""
    def __init__(self, keys):
        self._keys = tuple(keys)
        self._saved = {}

    def __enter__(self):
        for k in self._keys:
            self._saved[k] = os.environ.get(k)
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class OrtPathOverrideResolvesInBothLanguages(unittest.TestCase):
    def test_override_file_found_by_shell_and_python(self):
        if shutil.which("bash") is None:
            self.skipTest("bash unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            override = Path(tmp) / "libonnxruntime.so"
            override.touch()
            with _EnvSandbox(["ORT_DYLIB_PATH", "ORT_CANDIDATE_PATHS"]):
                os.environ["ORT_DYLIB_PATH"] = str(override)
                os.environ["ORT_CANDIDATE_PATHS"] = ""
                shell_out = self._run_detect_ort()
                py_out = self._run_python_resolver()
            self.assertEqual(shell_out, str(override))
            self.assertEqual(py_out, str(override))

    def _run_detect_ort(self):
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

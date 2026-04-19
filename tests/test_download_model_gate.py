"""BC4: download-model.sh gates download (non-interactive abort + consent).

In S5.1 the deferral banner was removed (the real backend now consumes the
model). The gate itself — non-interactive abort, y/N prompt — is still
required. The ScriptContainsGateWarning case now asserts the POSIX-only
warning rather than the old S5.1-deferral text.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "embedder" / "download-model.sh"


class NoninteractiveEnvAbortsWithExitCode2(unittest.TestCase):
    def test_ci_env_aborts(self):
        env = {"PATH": os.environ.get("PATH", ""), "CI": "1"}
        r = subprocess.run(
            ["bash", str(SCRIPT)], env=env, capture_output=True,
            text=True, timeout=10)
        self.assertEqual(r.returncode, 2)


class NoninteractiveVarAlsoAborts(unittest.TestCase):
    def test_noninteractive_env_aborts(self):
        env = {"PATH": os.environ.get("PATH", ""), "NONINTERACTIVE": "1"}
        r = subprocess.run(
            ["bash", str(SCRIPT)], env=env, capture_output=True,
            text=True, timeout=10)
        self.assertEqual(r.returncode, 2)


class ScriptContainsGateWarning(unittest.TestCase):
    def test_warning_mentions_posix_requirement(self):
        body = SCRIPT.read_text()
        self.assertIn("macOS or", body)
        self.assertIn("Windows is not supported", body)


class NegativeResponseCancels(unittest.TestCase):
    def test_no_response_aborts_without_download(self):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": "/tmp/bc4"}
        r = subprocess.run(
            ["bash", str(SCRIPT)], env=env, input="n\n",
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()

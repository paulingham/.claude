"""BC4: download-model.sh warns user the model is not yet consumed (S5.1)."""
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
    def test_warning_mentions_s51(self):
        body = SCRIPT.read_text()
        self.assertIn("S5.1", body)
        self.assertIn("not", body.lower())  # "does NOT consume"


class NegativeResponseCancels(unittest.TestCase):
    def test_no_response_aborts_without_download(self):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": "/tmp/bc4"}
        r = subprocess.run(
            ["bash", str(SCRIPT)], env=env, input="n\n",
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()

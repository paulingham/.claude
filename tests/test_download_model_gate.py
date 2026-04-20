"""BC4: download-model.sh gates download (CI abort + interactive consent).

S9 inverted NONINTERACTIVE semantics: CI=1 still aborts (no user present),
but NONINTERACTIVE=1 now proceeds without prompting so bootstrap can drive
the script from /project-setup. The interactive consent prompt still
applies when neither CI nor NONINTERACTIVE is set.
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


class NoninteractiveVarProceedsPastPrompt(unittest.TestCase):
    """S9 inversion: NONINTERACTIVE=1 skips the y/N prompt and continues.

    Requires HOME to be writable (bootstrap supplies a tempdir). On a
    bare env with no HOME, the script fails for unrelated reasons —
    that's fine; we only assert it got past the abort check.
    """
    def test_noninteractive_env_does_not_exit_with_abort_code(self):
        import tempfile
        with tempfile.TemporaryDirectory() as home:
            sentinel_dir = (
                f"{home}/.claude/models/bge-small-en-v1.5")
            os.makedirs(sentinel_dir, exist_ok=True)
            open(f"{sentinel_dir}/model.onnx", "a").close()
            env = {"PATH": os.environ.get("PATH", ""),
                   "HOME": home,
                   "NONINTERACTIVE": "1"}
            r = subprocess.run(
                ["bash", str(SCRIPT)], env=env, capture_output=True,
                text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)


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

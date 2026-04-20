"""Slice 15: download-model.sh — exists, executable, mentions key env vars."""
import os
import stat
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "embedder" / "download-model.sh"


class DownloadScriptExists(unittest.TestCase):
    def test_script_present_and_executable(self):
        self.assertTrue(SCRIPT.exists())
        mode = os.stat(SCRIPT).st_mode
        self.assertTrue(mode & stat.S_IXUSR)


class DownloadScriptMentionsEnv(unittest.TestCase):
    def test_script_documents_ort_and_model_paths(self):
        body = SCRIPT.read_text()
        self.assertIn("ORT_DYLIB_PATH", body)
        self.assertIn("BGE_MODEL_PATH", body)
        self.assertIn("embedder backfill", body.lower())


class DownloadScriptAdvertisesVerifyCommand(unittest.TestCase):
    def test_script_tells_user_to_run_doctor_to_verify(self):
        body = SCRIPT.read_text().lower()
        self.assertIn("doctor", body)
        self.assertIn("verify", body)


class DownloadScriptPrintsExportLinesOnStdout(unittest.TestCase):
    def test_running_script_emits_export_lines(self):
        import subprocess
        env = {"HOME": "/tmp", "PATH": os.environ.get("PATH", "")}
        # Pre-create a sentinel file so script skips the curl branch.
        sentinel_dir = "/tmp/.claude/models/bge-small-en-v1.5"
        os.makedirs(sentinel_dir, exist_ok=True)
        open(f"{sentinel_dir}/model.onnx", "a").close()
        try:
            r = subprocess.run(
                ["bash", str(SCRIPT)],
                env=env, input="y\n", capture_output=True,
                text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("export ORT_DYLIB_PATH=", r.stdout)
            self.assertIn("export BGE_MODEL_PATH=", r.stdout)
        finally:
            pass


class NoninteractiveProceedsSkippingPrompt(unittest.TestCase):
    """S9 slice 11a: NONINTERACTIVE=1 proceeds without prompting.

    Previously NONINTERACTIVE=1 aborted with exit 2 (S5 honesty gate).
    S5.1 shipped the real backend, so the gate is obsolete. Bootstrap
    relies on this inversion.
    """
    def test_noninteractive_env_runs_to_completion(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as home:
            sentinel_dir = (
                f"{home}/.claude/models/bge-small-en-v1.5")
            os.makedirs(sentinel_dir, exist_ok=True)
            open(f"{sentinel_dir}/model.onnx", "a").close()
            env = {"HOME": home,
                   "PATH": os.environ.get("PATH", ""),
                   "NONINTERACTIVE": "1"}
            r = subprocess.run(
                ["bash", str(SCRIPT)], env=env, capture_output=True,
                text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("export ORT_DYLIB_PATH=", r.stdout)


if __name__ == "__main__":
    unittest.main()

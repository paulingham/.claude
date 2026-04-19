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


if __name__ == "__main__":
    unittest.main()

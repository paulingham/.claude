"""Slice 16: embedder status JSON writer — atomic, has required keys."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))


class StatusWriteProducesJSON(unittest.TestCase):
    def test_writes_file_with_required_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "embedder-status.json"
            os.environ["CLAUDE_EMBEDDER_STATUS"] = str(path)
            try:
                from embedder import status
                status.write({"ok": True, "model": "bge", "dim": 384})
                payload = json.loads(path.read_text())
                self.assertIn("ok", payload)
                self.assertIn("model", payload)
                self.assertIn("dim", payload)
            finally:
                os.environ.pop("CLAUDE_EMBEDDER_STATUS", None)


class StatusWriteAtomic(unittest.TestCase):
    def test_no_tmp_file_left_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "embedder-status.json"
            os.environ["CLAUDE_EMBEDDER_STATUS"] = str(path)
            try:
                from embedder import status
                status.write({"ok": False, "error": "missing"})
                leftover = list(path.parent.glob("*.tmp"))
                self.assertEqual(leftover, [])
            finally:
                os.environ.pop("CLAUDE_EMBEDDER_STATUS", None)


if __name__ == "__main__":
    unittest.main()

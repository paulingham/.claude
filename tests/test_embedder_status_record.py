"""BC2: status.record_success / record_failure — atomic, merge-preserving."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))


class RecordSuccessStampsLastSuccessAt(unittest.TestCase):
    def test_success_writes_timestamp_field(self):
        with _status_path() as out:
            from embedder import status
            status.record_success("2026-04-19T10:00:00Z")
            payload = json.loads(out.read_text())
            self.assertEqual(payload["last_success_at"],
                             "2026-04-19T10:00:00Z")


class RecordFailureStampsErrorAndTimestamp(unittest.TestCase):
    def test_failure_writes_last_error_and_last_error_at(self):
        with _status_path() as out:
            from embedder import status
            status.record_failure("ORT_DYLIB_PATH not set",
                                  "2026-04-19T10:05:00Z")
            payload = json.loads(out.read_text())
            self.assertEqual(payload["last_error"],
                             "ORT_DYLIB_PATH not set")
            self.assertEqual(payload["last_error_at"],
                             "2026-04-19T10:05:00Z")


class RecordPreservesPriorFields(unittest.TestCase):
    def test_success_after_failure_keeps_error_history(self):
        with _status_path() as out:
            from embedder import status
            status.record_failure("boom", "2026-04-19T10:00:00Z")
            status.record_success("2026-04-19T10:05:00Z")
            payload = json.loads(out.read_text())
            self.assertEqual(payload["last_error"], "boom")
            self.assertEqual(payload["last_success_at"],
                             "2026-04-19T10:05:00Z")


class _status_path:
    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "s.json"
        os.environ["CLAUDE_EMBEDDER_STATUS"] = str(self.out)
        return self.out

    def __exit__(self, *a):
        os.environ.pop("CLAUDE_EMBEDDER_STATUS", None)
        self.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()

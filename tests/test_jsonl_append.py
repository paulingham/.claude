"""Shared JSONL appender — contract test.

Pins the contract for hooks/_lib/jsonl_append.py:
- append_jsonl(metrics_dir, filename, record) writes one newline-terminated
  JSON line to {metrics_dir}/{filename}.
- Creates metrics_dir if it does not exist.
- Appends (does not overwrite) on repeated calls.
- Record may include any JSON-serialisable types.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

from jsonl_append import append_jsonl  # noqa: E402


class TestAppendJsonl(unittest.TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="jsonl-append-"))

    def test_writes_newline_terminated_json_line(self):
        path = self.tmp / "out.jsonl"
        append_jsonl(str(self.tmp), "out.jsonl", {"a": 1, "b": "x"})
        content = path.read_text(encoding="utf-8")
        self.assertTrue(content.endswith("\n"))
        rec = json.loads(content.rstrip("\n"))
        self.assertEqual(rec, {"a": 1, "b": "x"})

    def test_creates_directory_if_missing(self):
        nested = self.tmp / "does" / "not" / "exist"
        append_jsonl(str(nested), "out.jsonl", {"k": "v"})
        self.assertTrue((nested / "out.jsonl").exists())

    def test_appends_on_repeated_calls(self):
        append_jsonl(str(self.tmp), "out.jsonl", {"i": 1})
        append_jsonl(str(self.tmp), "out.jsonl", {"i": 2})
        append_jsonl(str(self.tmp), "out.jsonl", {"i": 3})
        lines = (self.tmp / "out.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual([json.loads(l)["i"] for l in lines], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()

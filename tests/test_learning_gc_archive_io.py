"""IO helpers for learning_gc_archive: split, gzip-append, atomic rewrite."""
import gzip
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

import learning_gc_archive_io as io_mod  # noqa: E402


class SplitLinesByAge(unittest.TestCase):
    def test_groups_old_lines_by_calendar_month(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        old_a = (cutoff - timedelta(days=5)).isoformat()
        old_b_diff_month = (cutoff - timedelta(days=40)).isoformat()
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            obs = Path(tmp) / "obs.jsonl"
            obs.write_text(
                json.dumps({"timestamp": old_a, "k": "a"}) + "\n"
                + json.dumps({"timestamp": old_b_diff_month, "k": "b"}) + "\n"
                + json.dumps({"timestamp": recent, "k": "r"}) + "\n"
                + "garbage\n")
            keep, by_month = io_mod.split_lines_by_age(obs, cutoff)
        kept_kinds = []
        for line in keep:
            try:
                kept_kinds.append(json.loads(line).get("k"))
            except json.JSONDecodeError:
                kept_kinds.append("garbage")
        self.assertIn("r", kept_kinds)
        self.assertIn("garbage", kept_kinds)
        self.assertNotIn("a", kept_kinds)
        archived_total = sum(len(v) for v in by_month.values())
        self.assertEqual(archived_total, 2)


class AppendGz(unittest.TestCase):
    def test_appends_then_reads_back_all_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "sub" / "obs.jsonl.gz"
            io_mod.append_gz(f, ["a", "b"])
            io_mod.append_gz(f, ["c"])
            with gzip.open(f, "rt") as fh:
                self.assertEqual(fh.read().splitlines(), ["a", "b", "c"])


class AtomicWriteLines(unittest.TestCase):
    def test_writes_lines_atomically_overwriting_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "obs.jsonl"
            f.write_text("old1\nold2\n")
            io_mod.atomic_write_lines(f, ["new"])
            self.assertEqual(f.read_text(), "new\n")

    def test_empty_input_writes_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "obs.jsonl"
            f.write_text("anything\n")
            io_mod.atomic_write_lines(f, [])
            self.assertEqual(f.read_text(), "")


if __name__ == "__main__":
    unittest.main()

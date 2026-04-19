"""AC2b: scratchpad write path sanitizes body + applies privacy classifier."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from _support import count_rows  # noqa: F401 — puts _lib on sys.path
from _lib import live_writer, schema  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills"))
from capture._lib import privacy  # noqa: E402


class _AllowlistTmp:
    def __init__(self, data):
        self._data = data

    def __enter__(self):
        self._dir = tempfile.TemporaryDirectory()
        path = Path(self._dir.name) / "user.json"
        path.write_text(json.dumps(self._data))
        self._prev = privacy._user_path, privacy._default_path
        privacy._user_path, privacy._default_path = path, None
        return self

    def __exit__(self, *a):
        privacy._user_path, privacy._default_path = self._prev
        self._dir.cleanup()


def _row(db):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT body, is_private FROM scratchpad_findings").fetchone()
    finally:
        con.close()


def _finding(body="text", **overrides):
    base = {"task_id": "t1", "category": "discovery", "agent_role": "engineer",
            "phase": "build", "timestamp": "2026-04-19T00:00:00Z",
            "body": body}
    base.update(overrides)
    return base


class ScratchpadStripsPrivateTagFromBody(unittest.TestCase):
    """AC2b: <private> block in body is stripped before persist."""
    def test_body_private_tag_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "m.sqlite"
            schema.ensure(db)
            with _AllowlistTmp({"file_globs": [], "content_regexes": []}):
                live_writer.write_finding(
                    _finding("note <private>secret</private> end"), db)
            body, priv = _row(db)
            self.assertNotIn("<private>", body)
            self.assertNotIn("secret", body)
            self.assertEqual(priv, 0)


class ScratchpadFlagsAwsKeyInBody(unittest.TestCase):
    """AC4 scratchpad: AWS regex in body sets is_private=1."""
    def test_aws_key_body_private_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "m.sqlite"
            schema.ensure(db)
            with _AllowlistTmp({"file_globs": [],
                                "content_regexes": [r"AKIA[0-9A-Z]{16}\b"]}):
                live_writer.write_finding(
                    _finding("key=AKIAIOSFODNN7EXAMPLE"), db)
            self.assertEqual(_row(db)[1], 1)


if __name__ == "__main__":
    unittest.main()

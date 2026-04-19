"""AC2a, AC9: privacy wired into live_writer + ingest with dedup parity."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from _support import count_rows  # ensures _lib importable
from _lib import live_writer, ingest, schema  # noqa: E402

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
            "SELECT content_hash, is_private, searchable_text, file "
            "FROM observations").fetchone()
    finally:
        con.close()


class LiveWriterFlagsEnvFilePrivate(unittest.TestCase):
    """AC2a: .env file via live_writer → is_private=1."""
    def test_env_observation_persists_with_is_private_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            with _AllowlistTmp({"file_globs": [".env"], "content_regexes": []}):
                live_writer.write_one(
                    {"session_id": "s", "timestamp": "t", "tool": "Read",
                     "file": ".env", "outcome": "ok"}, db)
            self.assertEqual(_row(db)[1], 1)


class LiveWriterStripsPrivateTagFromOutcome(unittest.TestCase):
    """AC2a: outcome containing <private> is sanitized before searchable_text."""
    def test_outcome_private_tag_absent_from_searchable_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            with _AllowlistTmp({"file_globs": [], "content_regexes": []}):
                live_writer.write_one(
                    {"session_id": "s", "timestamp": "t", "tool": "Bash",
                     "file": "a.sh",
                     "outcome": "echo <private>SECRET</private> done"}, db)
            text = _row(db)[2]
            self.assertNotIn("<private>", text)
            self.assertNotIn("SECRET", text)


class LiveWriterFlagsAwsKeyInOutcome(unittest.TestCase):
    """AC4: AWS key pattern in outcome flags row as private."""
    def test_aws_key_outcome_is_private_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            with _AllowlistTmp({"file_globs": [],
                                "content_regexes": [r"AKIA[0-9A-Z]{16}\b"]}):
                live_writer.write_one(
                    {"session_id": "s", "timestamp": "t", "tool": "Bash",
                     "file": "", "outcome": "KEY=AKIAIOSFODNN7EXAMPLE"}, db)
            self.assertEqual(_row(db)[1], 1)


class LiveWriterSanitizesPrivateInFilePath(unittest.TestCase):
    """AC1 on file: <private> block in file is stripped before hash/persist."""
    def test_file_with_private_block_sanitized(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            with _AllowlistTmp({"file_globs": [], "content_regexes": []}):
                live_writer.write_one(
                    {"session_id": "s", "timestamp": "t", "tool": "Read",
                     "file": "<private>secret</private>.env",
                     "outcome": "ok"}, db)
            self.assertEqual(_row(db)[3], ".env")


class LiveAndIngestProduceIdenticalRow(unittest.TestCase):
    """AC9 / R9: live + replay paths yield identical content_hash + is_private."""
    def test_parity_across_live_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_live = Path(tmp) / "live.sqlite"
            db_replay = Path(tmp) / "replay.sqlite"
            schema.ensure(db_live)
            schema.ensure(db_replay)
            obj = {"session_id": "s", "timestamp": "t", "tool": "Read",
                   "file": ".env", "outcome": "ok"}
            with _AllowlistTmp({"file_globs": [".env"], "content_regexes": []}):
                live_writer.write_one(dict(obj), db_live)
                learning = Path(tmp) / "learning" / "proj"
                learning.mkdir(parents=True)
                (learning / "observations.jsonl").write_text(
                    json.dumps(obj) + "\n")
                ingest.ingest_all(db_replay, Path(tmp) / "learning")
            self.assertEqual(_row(db_live)[0], _row(db_replay)[0])
            self.assertEqual(_row(db_live)[1], _row(db_replay)[1])


if __name__ == "__main__":
    unittest.main()

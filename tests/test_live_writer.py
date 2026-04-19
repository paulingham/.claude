"""Acceptance-criterion tests for live_writer.py (Story 2 live writes)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _support import count_rows, reindex, write_jsonl
from _lib import live_writer, schema


def _obj(sid="s1", ts="2026-04-19T00:00:00Z", tool="Read", f="/a.py"):
    return {"session_id": sid, "timestamp": ts, "tool": tool,
            "file": f, "outcome": "success",
            "project_hash": "pha"}


class AC1InsertsOneRow(unittest.TestCase):
    def test_write_one_inserts_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            live_writer.write_one(_obj(), db)
            self.assertEqual(count_rows(db, "observations"), 1)


class AC2DedupByContentHash(unittest.TestCase):
    def test_same_key_twice_yields_one_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            live_writer.write_one(_obj(), db)
            live_writer.write_one(_obj(), db)
            self.assertEqual(count_rows(db, "observations"), 1)


class AC3ReindexAfterLiveIsNoop(unittest.TestCase):
    def test_reindex_inserts_zero_after_live_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, learning = _live_then_mirror_jsonl(tmp)
            summary = reindex.run(db_path=db, learning_root=learning)
            self.assertEqual(summary.inserted, 0)
            self.assertEqual(count_rows(db, "observations"), 3)


def _live_then_mirror_jsonl(tmp):
    db = Path(tmp) / "memory.sqlite"
    learning = Path(tmp) / "learning"
    schema.ensure(db)
    objs = _three_objs()
    for o in objs:
        live_writer.write_one(o, db)
    write_jsonl(learning / "pha" / "observations.jsonl", objs)
    return db, learning


class AC7IsPrivateZero(unittest.TestCase):
    def test_inserted_row_has_is_private_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "memory.sqlite"
            schema.ensure(db)
            live_writer.write_one(_obj(), db)
            self.assertEqual(_first_is_private(db), 0)


def _first_is_private(db):
    con = sqlite3.connect(str(db))
    try:
        return con.execute(
            "SELECT is_private FROM observations LIMIT 1").fetchone()[0]
    finally:
        con.close()


def _three_objs():
    return [_obj(ts="2026-04-19T00:00:00Z", tool="Read", f="/a.py"),
            _obj(ts="2026-04-19T00:00:01Z", tool="Edit", f="/a.py"),
            _obj(ts="2026-04-19T00:00:02Z", tool="Bash", f="")]


if __name__ == "__main__":
    unittest.main()

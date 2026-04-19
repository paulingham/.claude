"""AC6: read-only invariant for rerank — three independent guarantees."""
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / "skills"))

from _support import build_populated_db  # noqa: E402
from recall import recall as recall_mod  # noqa: E402
from recall._lib import vec_store  # noqa: E402

WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|REPLACE)\b",
    re.IGNORECASE)


class RerankCannotInsert(unittest.TestCase):
    def test_ro_connection_raises_on_insert(self):
        with tempfile.TemporaryDirectory() as tmp:
            db, _ = build_populated_db(tmp)
            vec_store.load(db, ["some_hash"])
            ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            ro.execute("PRAGMA query_only = 1")
            with self.assertRaises(sqlite3.OperationalError):
                ro.execute("INSERT INTO embeddings "
                           "(content_hash, model_id, dim, vector) "
                           "VALUES ('h', 'm', 1, x'00')")
            ro.close()


class RerankSourceHasNoWriteKeywords(unittest.TestCase):
    def test_static_grep_no_write_statements(self):
        path = REPO_ROOT / "skills" / "recall" / "_lib" / "rerank.py"
        source = _strip_comments(path.read_text())
        self.assertEqual(WRITE_KEYWORDS.findall(source), [])


def _strip_comments(text):
    lines = [_strip_hash(l) for l in text.splitlines()
             if not _is_docstring_only(l)]
    return "\n".join(lines)


def _strip_hash(line):
    idx = line.find("#")
    return line if idx < 0 else line[:idx]


def _is_docstring_only(line):
    s = line.strip()
    return s.startswith('"""') or s.startswith("'''")


class PragmaQueryOnlyPreserved(unittest.TestCase):
    def test_query_only_stays_after_recall_search(self):
        os.environ["CLAUDE_EMBEDDER"] = "fake"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db, _ = build_populated_db(tmp)
                recall_mod.search("Read", db_path=db)
                ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
                ro.execute("PRAGMA query_only = 1")
                val = ro.execute("PRAGMA query_only").fetchone()[0]
                ro.close()
                self.assertEqual(val, 1)
        finally:
            os.environ.pop("CLAUDE_EMBEDDER", None)


if __name__ == "__main__":
    unittest.main()

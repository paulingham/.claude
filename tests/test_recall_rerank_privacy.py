"""AC5: privacy gate survives rerank — filter runs before embeddings lookup.

Seeds a private observation WITH a stored embedding, then asserts that:
(a) include_private=False hides it even though a vector exists; rerank never
    sees a private row — the FTS5 `WHERE is_private = 0` runs upstream.
(b) include_private=True returns it — semantic path works when unlocked.
"""
import os
import sqlite3
import struct
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))
sys.path.insert(0, str(REPO_ROOT / "skills"))

from _support import build_populated_db_with_private_row  # noqa: E402
from recall import recall as recall_mod  # noqa: E402


def _unit_vec(first=1.0, dim=384):
    tail = [0.0] * (dim - 1)
    return struct.pack(f"<{dim}f", first, *tail)


def _insert_embedding(db, content_hash, vector):
    con = sqlite3.connect(str(db))
    try:
        con.execute(
            "INSERT INTO embeddings (content_hash, model_id, dim, vector) "
            "VALUES (?, 'bge-small-en-v1.5', 384, ?)",
            (content_hash, vector))
        con.commit()
    finally:
        con.close()


class PrivateRowHiddenDespiteEmbedding(unittest.TestCase):
    def test_include_private_false_blocks_private_semantic_match(self):
        os.environ["CLAUDE_EMBEDDER"] = "fake"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db, _ = build_populated_db_with_private_row(tmp)
                _insert_embedding(db, "privhash", _unit_vec())
                hits = recall_mod.search(
                    "Secret", db_path=db, source="observations")
                self.assertEqual(hits, [])
        finally:
            os.environ.pop("CLAUDE_EMBEDDER", None)


class PrivateRowVisibleWhenUnlocked(unittest.TestCase):
    def test_include_private_true_surfaces_private_row(self):
        os.environ["CLAUDE_EMBEDDER"] = "fake"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                db, _ = build_populated_db_with_private_row(tmp)
                _insert_embedding(db, "privhash", _unit_vec())
                hits = recall_mod.search(
                    "Secret", db_path=db, source="observations",
                    include_private=True)
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]["tool"], "Secret")
        finally:
            os.environ.pop("CLAUDE_EMBEDDER", None)


if __name__ == "__main__":
    unittest.main()

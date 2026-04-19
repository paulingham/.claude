"""Rerank with hand-crafted vectors — AC4a + AC4b + shape + mixed-source."""
import sqlite3
import struct
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)
_TESTS = str(REPO_ROOT / "tests")
if _TESTS not in sys.path:
    sys.path.insert(0, _TESTS)

from embedder._lib.fake import FakeEmbedder  # noqa: E402
from recall._lib import rerank  # noqa: E402


def _vec(first_three, dim=384):
    tail = [0.0] * (dim - len(first_three))
    return list(first_three) + tail


def _query_vec():
    return _vec([1.0, 0.0, 0.0])


def _row_a():
    return _vec([0.9, 0.436, 0.0])   # dot=0.9 vs q (unit ~1.0)


def _row_b():
    return _vec([0.1, 0.995, 0.0])   # dot=0.1


def _row_c():
    return _vec([0.8, 0.6, 0.0])     # dot=0.8


def _store_vec(con, content_hash, floats):
    blob = struct.pack("<384f", *floats)
    con.execute(
        "INSERT INTO embeddings (content_hash, model_id, dim, vector) "
        "VALUES (?, 'bge-small-en-v1.5', 384, ?)", (content_hash, blob))


def _seed_three(con):
    _store_vec(con, "ha", _row_a())
    _store_vec(con, "hb", _row_b())
    _store_vec(con, "hc", _row_c())


def _candidates(shape="obs"):
    key = "file" if shape == "obs" else "category"
    return [
        {"id": 1, "content_hash": "ha", key: "f.py", "tool": "Read"},
        {"id": 2, "content_hash": "hb", key: "f.py", "tool": "Read"},
        {"id": 3, "content_hash": "hc", key: "f.py", "tool": "Read"},
    ]


def _tmpdb():
    fd = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    fd.close()
    con = sqlite3.connect(fd.name)
    con.execute("CREATE TABLE embeddings (content_hash TEXT PRIMARY KEY, "
                "model_id TEXT, dim INTEGER, vector BLOB)")
    return fd.name, con


class SemanticPromotion(unittest.TestCase):
    def test_promotes_semantic_match(self):
        db, con = _tmpdb()
        _seed_three(con)
        con.commit()
        con.close()
        emb = FakeEmbedder(vectors={"q": _query_vec()})
        hits, unavail = rerank.rerank(db, _candidates(), "q", 3, emb)
        self.assertFalse(unavail)
        self.assertEqual([h["content_hash"] for h in hits], ["ha", "hc", "hb"])


class MissingEmbeddingKeepsBm25(unittest.TestCase):
    def test_rows_without_embedding_retain_bm25(self):
        db, con = _tmpdb()
        _store_vec(con, "ha", _row_a())
        con.commit()
        con.close()
        emb = FakeEmbedder(vectors={"q": _query_vec()})
        hits, _ = rerank.rerank(db, _candidates(), "q", 3, emb)
        self.assertEqual(len(hits), 3)
        got = [h["content_hash"] for h in hits]
        self.assertEqual(got[0], "ha")


class ScratchpadShapePreserved(unittest.TestCase):
    def test_category_source_keys_intact(self):
        db, con = _tmpdb()
        _seed_three(con)
        con.commit()
        con.close()
        sp = [
            {"id": 1, "content_hash": "ha", "category": "discovery",
             "source": "scratchpad"},
            {"id": 2, "content_hash": "hb", "category": "warning",
             "source": "scratchpad"},
        ]
        emb = FakeEmbedder(vectors={"q": _query_vec()})
        hits, _ = rerank.rerank(db, sp, "q", 2, emb)
        self.assertEqual(hits[0]["category"], "discovery")
        self.assertEqual(hits[0]["source"], "scratchpad")


class EmbedderFailureSignalsUnavailable(unittest.TestCase):
    def test_encode_failure_returns_unavailable_true(self):
        db, con = _tmpdb()
        _seed_three(con)
        con.commit()
        con.close()

        class Broken:
            def encode(self, _):
                raise RuntimeError("boom")

        hits, unavail = rerank.rerank(db, _candidates(), "q", 2, Broken())
        self.assertTrue(unavail)
        self.assertEqual(len(hits), 2)


if __name__ == "__main__":
    unittest.main()

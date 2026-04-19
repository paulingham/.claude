"""D2 regression: search_tier hash width must match embeddings hash width.

Previously search_tier returned substr(content_hash, 1, 16) while embeddings
stores the full 64-char sha256 → vec_store.load always returned {} and
rerank.cosine was always 0.0. This test exercises the full path and asserts
that the stored embedding actually contributes to the rerank blend."""
import hashlib
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

from recall._lib import rerank, search_tier  # noqa: E402


def _schema(con):
    con.executescript((REPO_ROOT / "db" / "schema.sql").read_text())


def _h(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _insert_obs(con, text):
    h = _h(text)
    con.execute(
        "INSERT INTO observations (content_hash, session_id, timestamp, "
        "tool, searchable_text) VALUES (?, 's', '2026-04-01T00:00:00Z', "
        "'Read', ?)", (h, text))
    return h


def _vec(first, dim=384):
    return list(first) + [0.0] * (dim - len(first))


def _insert_vec(con, content_hash, floats):
    blob = struct.pack("<384f", *floats)
    con.execute(
        "INSERT INTO embeddings (content_hash, model_id, dim, vector) "
        "VALUES (?, 'bge-small-en-v1.5', 384, ?)", (content_hash, blob))


class FakeQ:
    def __init__(self, floats):
        self.bytes = struct.pack("<384f", *floats)

    def encode(self, _):
        return self.bytes


def _tmpdb():
    fd = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    fd.close()
    con = sqlite3.connect(fd.name)
    _schema(con)
    return fd.name, con


class FullHashRoundTripDrivesCosine(unittest.TestCase):
    """The low-bm25 candidate should win rerank when its embedding aligns
    with the query vector. This proves cosine contributes to the blend.

    Fails today: vec_store.load returns {} for every candidate (candidate
    hash is 16-char prefix; embeddings stores 64-char full)."""

    def test_aligned_vector_wins_rerank(self):
        db, con = _tmpdb()
        h_a = _insert_obs(con, "alpha alpha alpha alpha alpha")
        h_b = _insert_obs(con, "alpha beta")
        _insert_vec(con, h_a, _vec([0.0, 1.0]))
        _insert_vec(con, h_b, _vec([1.0, 0.0]))
        con.commit()
        con.close()
        hits = search_tier.search_observations(db, "alpha", limit=10)
        self.assertEqual(len(hits), 2)
        q = FakeQ(_vec([1.0, 0.0]))
        reranked, unavail = rerank.rerank(db, hits, "alpha", 2, q)
        self.assertFalse(unavail)
        top_text = next(
            r for r in _read_texts(db) if r[0] == reranked[0]["id"])[1]
        self.assertIn("beta", top_text)


def _read_texts(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute(
            "SELECT id, searchable_text FROM observations").fetchall()
    finally:
        con.close()


if __name__ == "__main__":
    unittest.main()

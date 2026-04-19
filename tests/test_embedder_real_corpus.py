"""Slice 8: BM25 vs BM25+cosine recall@5 on 50-obs corpus (AC4)."""
import hashlib
import json
import os
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

_FIXTURE = (REPO_ROOT / "skills" / "embedder" / "tests" / "fixtures"
            / "s5_1_corpus.jsonl")
_SCHEMA = REPO_ROOT / "db" / "schema.sql"


def _env_ok():
    return bool(os.environ.get("BGE_MODEL_PATH")) and \
        bool(os.environ.get("ORT_DYLIB_PATH"))


def _load_corpus():
    return [json.loads(l) for l in _FIXTURE.read_text().splitlines() if l]


def _seed_db(db_path, rows, embedder):
    con = sqlite3.connect(str(db_path))
    con.executescript(_SCHEMA.read_text())
    for row in rows:
        h = hashlib.sha256(row["id"].encode()).hexdigest()
        text = row["text"]
        con.execute(
            "INSERT INTO observations (content_hash, session_id, timestamp,"
            " tool, searchable_text) VALUES (?, 's', '2026-01-01T00:00:00Z',"
            " 'Write', ?)", (h, text))
        vec = embedder.encode(text)
        con.execute(
            "INSERT INTO embeddings (content_hash, model_id, dim, vector) "
            "VALUES (?, 'bge', 384, ?)", (h, vec))
    con.commit()
    con.close()


def _bm25_ranks(db_path, query, limit=20):
    from recall._lib import dispatch
    hits = dispatch.search(query, limit, "observations", str(db_path),
                           False, None)
    return [h["content_hash"] for h in hits]


def _rerank_top5(db_path, query, embedder):
    from recall._lib import rerank, dispatch
    hits = dispatch.search(query, 20, "observations", str(db_path),
                           False, None)
    out, _ = rerank.rerank(str(db_path), hits, query, 5, embedder)
    return [h["content_hash"] for h in out]


@unittest.skipUnless(_env_ok(), "ORT_DYLIB_PATH/BGE_MODEL_PATH unset")
class CorpusBaselineSeededCorrectly(unittest.TestCase):
    def test_each_target_is_ranked_6_to_10_under_bm25_alone(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "m.sqlite"
            embedder = _fresh_embedder()
            _seed_db(db, _load_corpus(), embedder)
            for t in _targets():
                rank = _rank_of(t, db)
                self.assertTrue(6 <= rank <= 10,
                                f"{t['id']} rank={rank} outside [6,10]")


@unittest.skipUnless(_env_ok(), "ORT_DYLIB_PATH/BGE_MODEL_PATH unset")
class RerankImprovesRecallAt5OnAtLeastThreeOfFive(unittest.TestCase):
    def test_at_least_three_of_five_queries_recall_target_with_rerank(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "m.sqlite"
            embedder = _fresh_embedder()
            _seed_db(db, _load_corpus(), embedder)
            wins = sum(_improved(t, db, embedder) for t in _targets())
            self.assertGreaterEqual(wins, 3, f"wins={wins} of 5")


def _targets():
    return [r for r in _load_corpus() if r["id"].endswith("_target")]


def _rank_of(target, db_path):
    h = hashlib.sha256(target["id"].encode()).hexdigest()
    ranks = _bm25_ranks(db_path, target["query"])
    return ranks.index(h) + 1 if h in ranks else 99


def _improved(target, db_path, embedder):
    h = hashlib.sha256(target["id"].encode()).hexdigest()
    return h in _rerank_top5(db_path, target["query"], embedder)


def _fresh_embedder():
    os.environ.pop("CLAUDE_EMBEDDER", None)
    from embedder.embedder import get_embedder, reset_singleton_for_tests
    reset_singleton_for_tests()
    return get_embedder()


if __name__ == "__main__":
    unittest.main()

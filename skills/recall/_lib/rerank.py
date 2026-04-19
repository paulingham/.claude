"""Semantic rerank of FTS5 candidates using stored float32 embeddings.

Pure read path: vec_store opens read-only + PRAGMA query_only=1.
Returns (hits, unavailable); unavailable=True flips recall.py into AC11
banner mode."""
import struct

from recall._lib import rerank_blend, vec_store

DIM = rerank_blend.DIM


def rerank(db_path, candidates, query, limit, embedder):
    qbytes = _encode(query, embedder)
    if qbytes is None:
        return [_strip(c) for c in candidates[:limit]], True
    keys = [_key(c) for c in candidates]
    vectors = vec_store.load(db_path, keys)
    return _sort(candidates, keys, qbytes, vectors, limit), False


def _encode(query, embedder):
    try:
        return embedder.encode(query)
    except Exception:
        return None


def _sort(candidates, keys, qbytes, vectors, limit):
    q = struct.unpack(f"<{DIM}f", qbytes)
    scored = [(rerank_blend.blend(i, q, vectors.get(keys[i])), c)
              for i, c in enumerate(candidates)]
    ordered = [c for _, c in sorted(scored, key=lambda p: -p[0])[:limit]]
    return [_strip(c) for c in ordered]


def _key(candidate):
    return candidate.get("_full_hash") or candidate["content_hash"]


def _strip(candidate):
    return {k: v for k, v in candidate.items() if not k.startswith("_")}

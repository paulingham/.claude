"""Semantic rerank of FTS5 candidates using stored float32 embeddings.

Pure read path: vec_store opens read-only + PRAGMA query_only=1.
Returns (hits, unavailable); unavailable=True flips recall.py into AC11
banner mode."""
import struct

from recall._lib import vec_store

DEFAULT_ALPHA = 0.5
DIM = 384


def rerank(db_path, candidates, query, limit, embedder):
    qbytes = _encode(query, embedder)
    if qbytes is None:
        return candidates[:limit], True
    vectors = vec_store.load(db_path, [c["content_hash"] for c in candidates])
    return _sort(candidates, qbytes, vectors, limit), False


def _encode(query, embedder):
    try:
        return embedder.encode(query)
    except Exception:
        return None


def _sort(candidates, qbytes, vectors, limit):
    q = struct.unpack(f"<{DIM}f", qbytes)
    scored = [(_blend(i, q, vectors.get(c["content_hash"])), c)
              for i, c in enumerate(candidates)]
    return [c for _, c in sorted(scored, key=lambda p: -p[0])[:limit]]


def _blend(idx, q, row_bytes):
    cos = _cosine(q, row_bytes) if row_bytes else 0.0
    return DEFAULT_ALPHA / (1.0 + idx) + (1.0 - DEFAULT_ALPHA) * cos


def _cosine(q, row_bytes):
    row = struct.unpack(f"<{DIM}f", row_bytes)
    return sum(a * b for a, b in zip(q, row))

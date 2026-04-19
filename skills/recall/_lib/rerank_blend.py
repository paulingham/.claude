"""Blend BM25 position with cosine similarity.

blend(i, q, row) = alpha/(1+i) + (1-alpha)*cos(q, row). When row is missing
cosine contribution is 0 — candidate degrades to pure BM25 rank."""
import struct

DEFAULT_ALPHA = 0.5
DIM = 384


def blend(idx, q, row_bytes):
    cos = _cosine(q, row_bytes) if row_bytes else 0.0
    return DEFAULT_ALPHA / (1.0 + idx) + (1.0 - DEFAULT_ALPHA) * cos


def _cosine(q, row_bytes):
    row = struct.unpack(f"<{DIM}f", row_bytes)
    return sum(a * b for a, b in zip(q, row))

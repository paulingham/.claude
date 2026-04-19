"""FakeEmbedder: deterministic 384-d test double + optional dict override."""
import hashlib
import struct

DIM = 384


class FakeEmbedder:
    def __init__(self, vectors=None):
        self.vectors = vectors or {}

    def encode(self, text):
        return _pack(self.vectors[text]) if text in self.vectors \
            else _hash_vec(text)


def _hash_vec(text):
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    floats = [_byte_to_float(seed[i % len(seed)]) for i in range(DIM)]
    return _pack(_normalise(floats))


def _byte_to_float(b):
    return (b - 128) / 128.0


def _normalise(floats):
    n = sum(f * f for f in floats) ** 0.5 or 1.0
    return [f / n for f in floats]


def _pack(floats):
    return struct.pack(f"<{DIM}f", *_normalise(list(floats)))

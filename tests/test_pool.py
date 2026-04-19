"""Slice 5c: mean_pool_l2 packs 1536 bytes of unit-norm float32 vector."""
import math
import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


class MeanPoolL2(unittest.TestCase):
    def test_output_is_1536_bytes(self):
        from embedder._lib import pool
        raw = [1.0] * (4 * 384)
        out = pool.mean_pool_l2(raw, 4, [1, 1, 1, 1])
        self.assertEqual(len(out), 1536)

    def test_output_has_unit_l2_norm(self):
        from embedder._lib import pool
        raw = _raw_with_nonzero(4, 384)
        out = pool.mean_pool_l2(raw, 4, [1, 1, 1, 0])
        unpacked = struct.unpack("<384f", out)
        norm_sq = sum(x * x for x in unpacked)
        self.assertTrue(abs(norm_sq - 1.0) < 1e-5, norm_sq)

    def test_all_zero_mask_returns_zero_vector(self):
        from embedder._lib import pool
        raw = [0.0] * (2 * 384)
        out = pool.mean_pool_l2(raw, 2, [0, 0])
        unpacked = struct.unpack("<384f", out)
        self.assertTrue(all(x == 0.0 for x in unpacked))


def _raw_with_nonzero(seq, dim):
    data = []
    for t in range(seq):
        data.extend(float(t + 1) for _ in range(dim))
    return data


if __name__ == "__main__":
    unittest.main()

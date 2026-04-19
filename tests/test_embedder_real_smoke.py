"""Slice 5d: real embedder end-to-end — 1536 bytes, unit L2 norm."""
import os
import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))


def _real_available():
    return bool(os.environ.get("BGE_MODEL_PATH")) and \
        bool(os.environ.get("ORT_DYLIB_PATH"))


@unittest.skipUnless(_real_available(), "BGE_MODEL_PATH/ORT_DYLIB_PATH unset")
class RealEmbedderEncodesDim384(unittest.TestCase):
    def test_encode_returns_1536_bytes_unit_norm(self):
        os.environ.pop("CLAUDE_EMBEDDER", None)
        from embedder.embedder import get_embedder, reset_singleton_for_tests
        reset_singleton_for_tests()
        try:
            vec = get_embedder().encode("hello world")
            self.assertEqual(len(vec), 1536)
            norm_sq = sum(x * x for x in struct.unpack("<384f", vec))
            self.assertTrue(abs(norm_sq - 1.0) < 1e-4, norm_sq)
        finally:
            reset_singleton_for_tests()


if __name__ == "__main__":
    unittest.main()

"""Slice 14: real embedder smoke — skipped unless BGE_MODEL_PATH is set.

Exercises the real ORT backend end-to-end on the deferred Slice 4 stub.
When real backend lands in S5.1/S7, this skip disappears automatically.
"""
import os
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
    def test_encode_returns_384_floats(self):
        os.environ.pop("CLAUDE_EMBEDDER", None)
        from embedder.embedder import get_embedder, reset_singleton_for_tests
        reset_singleton_for_tests()
        vec = get_embedder().encode("hello world")
        self.assertEqual(len(vec), 384 * 4)


if __name__ == "__main__":
    unittest.main()

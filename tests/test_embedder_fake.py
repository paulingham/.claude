"""FakeEmbedder contract — deterministic 384-d output + dict injection."""
import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)

from embedder._lib.fake import FakeEmbedder  # noqa: E402


class EncodeShape(unittest.TestCase):
    def test_encode_returns_1536_bytes(self):
        vec = FakeEmbedder().encode("hello world")
        self.assertIsInstance(vec, bytes)
        self.assertEqual(len(vec), 384 * 4)


class EncodeDeterministic(unittest.TestCase):
    def test_same_input_same_output(self):
        fake = FakeEmbedder()
        self.assertEqual(fake.encode("x"), fake.encode("x"))


class EncodeUnitNorm(unittest.TestCase):
    def test_l2_norm_is_one(self):
        vec = FakeEmbedder().encode("anything")
        floats = struct.unpack("<384f", vec)
        n = sum(f * f for f in floats) ** 0.5
        self.assertAlmostEqual(n, 1.0, places=5)


class DictOverride(unittest.TestCase):
    def test_vectors_override_takes_precedence(self):
        override = [1.0] + [0.0] * 383
        fake = FakeEmbedder(vectors={"text_a": override})
        got = struct.unpack("<384f", fake.encode("text_a"))
        self.assertEqual(got[0], 1.0)
        self.assertEqual(got[1], 0.0)


if __name__ == "__main__":
    unittest.main()

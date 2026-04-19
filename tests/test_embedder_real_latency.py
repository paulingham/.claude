"""Slice 10: AC7 — real embedder median encode latency <= 15ms.

Protocol: 5 warmup calls (discarded) + 100 timed calls. Assert median <= 15.0ms.
Env-gated: skipped unless ORT_DYLIB_PATH + BGE_MODEL_PATH set AND an actual
libonnxruntime dylib + bge-small-en-v1.5 model are on disk.
"""
import os
import statistics
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


def _env_ok():
    return bool(os.environ.get("BGE_MODEL_PATH")) and \
        bool(os.environ.get("ORT_DYLIB_PATH"))


def _fresh_embedder():
    os.environ.pop("CLAUDE_EMBEDDER", None)
    from embedder.embedder import get_embedder, reset_singleton_for_tests
    reset_singleton_for_tests()
    return get_embedder()


def _measure_median_ms(embedder, text, n):
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        embedder.encode(text)
        samples.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(samples)


@unittest.skipUnless(_env_ok(), "ORT_DYLIB_PATH/BGE_MODEL_PATH unset")
class RealEmbedderMedianEncodeLatencyAt128Tokens(unittest.TestCase):
    def test_median_encode_latency_under_15ms_at_128_tokens(self):
        embedder = _fresh_embedder()
        sample_text = "the quick brown fox jumps over the lazy dog " * 8
        for _ in range(5):
            embedder.encode(sample_text)
        median_ms = _measure_median_ms(embedder, sample_text, 100)
        self.assertLessEqual(
            median_ms, 15.0,
            f"median encode latency={median_ms:.2f}ms exceeds 15ms (AC7)")


if __name__ == "__main__":
    unittest.main()

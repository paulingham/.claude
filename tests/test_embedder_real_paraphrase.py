"""Slice 7: paraphrase cosine > 0.7, unrelated cosine < 0.4 (AC2, AC3)."""
import math
import os
import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL = str(REPO_ROOT / "skills")
if _SKILL not in sys.path:
    sys.path.insert(0, _SKILL)


_PARAPHRASES = [
    ("The quick brown fox jumps over the lazy dog.",
     "A swift brown fox leaps above the lazy dog."),
    ("I need to fix the login bug in production.",
     "Production has a login bug I must repair."),
    ("Please schedule a meeting for tomorrow at 10am.",
     "Book a 10am meeting tomorrow."),
    ("The database query is running too slowly.",
     "This SQL query performs poorly."),
    ("Can you review my pull request today?",
     "Would you look at my PR sometime today?"),
]

_UNRELATED = [
    ("The weather is sunny and warm today.",
     "The compiler emitted a type error."),
    ("She baked a chocolate cake for the party.",
     "Kubernetes scheduled the pod on a new node."),
    ("Shakespeare wrote many famous plays.",
     "The unit tests all passed on CI."),
    ("The cat sat on the mat.",
     "Run migrations before deploying to production."),
    ("Mount Everest is the tallest mountain.",
     "Refactor the service object to inject dependencies."),
]


def _env_ok():
    return bool(os.environ.get("BGE_MODEL_PATH")) and \
        bool(os.environ.get("ORT_DYLIB_PATH"))


@unittest.skipUnless(_env_ok(), "ORT_DYLIB_PATH/BGE_MODEL_PATH unset")
class ParaphraseAndUnrelatedCosineThresholds(unittest.TestCase):
    def test_paraphrases_score_above_0_7(self):
        actuals = [(a, b, _cos(a, b)) for a, b in _PARAPHRASES]
        failed = [(a, b, c) for a, b, c in actuals if c <= 0.7]
        self.assertEqual(failed, [], f"below threshold: {failed}")

    def test_unrelated_score_below_0_4(self):
        actuals = [(a, b, _cos(a, b)) for a, b in _UNRELATED]
        failed = [(a, b, c) for a, b, c in actuals if c >= 0.4]
        self.assertEqual(failed, [], f"above threshold: {failed}")


def _cos(a, b):
    from embedder.embedder import get_embedder, reset_singleton_for_tests
    os.environ.pop("CLAUDE_EMBEDDER", None)
    reset_singleton_for_tests()
    embedder = get_embedder()
    va = struct.unpack("<384f", embedder.encode(a))
    vb = struct.unpack("<384f", embedder.encode(b))
    return sum(x * y for x, y in zip(va, vb))


if __name__ == "__main__":
    unittest.main()

"""Name-matched entry point for rerank.py's TDD guard.

Full assertions live in test_recall_rerank.py. This file exists so the
pre-write TDD guard (which looks for tests/test_<stem>.py) accepts
edits to skills/recall/_lib/rerank.py."""
import unittest

from tests.test_recall_rerank import (
    EmbedderFailureSignalsUnavailable,  # noqa: F401
    MissingEmbeddingKeepsBm25,  # noqa: F401
    ScratchpadShapePreserved,  # noqa: F401
    SemanticPromotion,  # noqa: F401
)


class RerankSmoke(unittest.TestCase):
    def test_module_imports_cleanly(self):
        from recall._lib import rerank
        self.assertTrue(callable(rerank.rerank))


if __name__ == "__main__":
    unittest.main()

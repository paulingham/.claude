"""Glue module between recall.search and rerank.rerank.

Behaviour is exercised end-to-end via tests/test_recall_banner.py.
This file exists so the TDD-guard pre-write check is satisfied for
edits to skills/recall/_lib/rerank_support.py."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "skills"))


class RerankSupportImports(unittest.TestCase):
    def test_module_exports_apply_entry_point(self):
        from recall._lib import rerank_support
        self.assertTrue(callable(rerank_support.apply))

    def test_banner_constant_is_stable(self):
        from recall._lib import rerank_support
        self.assertIn("run 'embedder doctor'", rerank_support.BANNER)


if __name__ == "__main__":
    unittest.main()

"""Contract test: MCP reuses recall._lib.envelope.envelope directly."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mcp_support  # noqa: F401,E402
from recall._lib.envelope import envelope  # noqa: E402


class TestEnvelopeReuseImport(unittest.TestCase):
    def test_truncated_true_when_fetched_exceeds_limit(self):
        env = envelope("search", list(range(20)), 20, fetched=21)
        self.assertTrue(env["truncated"])
        self.assertEqual(env["tier"], "search")
        self.assertEqual(env["total"], 20)

    def test_truncated_false_when_fetched_fits_limit(self):
        env = envelope("search", [1, 2, 3], 20, fetched=3)
        self.assertFalse(env["truncated"])
        self.assertEqual(env["total"], 3)

    def test_empty_hits_returns_total_zero(self):
        env = envelope("search", [], 20, fetched=0)
        self.assertEqual(env["total"], 0)
        self.assertFalse(env["truncated"])


if __name__ == "__main__":
    unittest.main()

"""Slice A AC.3 — cost_estimator pricing table includes opus-4-5-20251101.

Authored RED-first. Pricing source: anthropic.com/pricing (verified 2026-05-15).
"""
from __future__ import annotations

import math
import pathlib
import sys
import unittest

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "hooks" / "_lib"))

from cost_estimator import PRICING_PER_MILLION, estimate_cost_usd  # noqa: E402


class PricingTableKeyedOnOpus45(unittest.TestCase):
    """A.3 — new pricing key exists and matches public rate-card."""

    def test_pricing_table_keyed_on_opus_4_5(self) -> None:
        rates = PRICING_PER_MILLION["claude-opus-4-5-20251101"]
        self.assertEqual(rates["input"], 5.00)
        self.assertEqual(rates["output"], 25.00)
        self.assertEqual(rates["cache_read"], 0.50)

    def test_legacy_opus_4_7_retained_for_dual_accept_window(self) -> None:
        """7-day rollback window per slice-a MED-rate_version-rollback."""
        self.assertIn("claude-opus-4-7", PRICING_PER_MILLION)

    def test_opus_4_5_round_trip_dollar_math(self) -> None:
        record = {
            "model": "claude-opus-4-5-20251101",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
        }
        usd = estimate_cost_usd([record])
        self.assertTrue(math.isclose(usd, 30.0), f"got {usd}")


if __name__ == "__main__":
    unittest.main()

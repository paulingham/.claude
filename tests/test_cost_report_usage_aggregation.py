"""ATDD tests — cost-report aggregation maps usage_by_model → non-zero USD.

AC5: given a costs.jsonl with usage_by_model, the aggregation helper
produces a NON-zero USD value via cost_estimator.estimate_cost_usd.

This was $0.00 before Slice 2 because real token usage was never captured.
"""
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))


class CostReportAggregationNonZero(unittest.TestCase):
    """AC5 — usage_by_model in session_end record maps to real USD."""

    def test_usage_by_model_to_estimate_cost_usd_nonzero(self):
        from cost_estimator import estimate_cost_usd
        # Build per-model records from a known usage_by_model dict
        usage_by_model = {
            "claude-opus-4-8": {
                "input_tokens": 100_000,
                "output_tokens": 10_000,
                "cache_read_input_tokens": 50_000,
                "cache_creation_input_tokens": 0,
            }
        }
        records = _usage_by_model_to_records(usage_by_model)
        usd = estimate_cost_usd(records)
        # 100k input @ $5/M = $0.50, 10k output @ $25/M = $0.25, 50k cache_read @ $0.50/M = $0.025
        # Total ≈ $0.775
        self.assertGreater(usd, 0.0, "expected non-zero USD from usage_by_model records")

    def test_empty_usage_by_model_returns_zero(self):
        from cost_estimator import estimate_cost_usd
        usd = estimate_cost_usd(_usage_by_model_to_records({}))
        self.assertEqual(usd, 0.0)

    def test_two_model_usage_sums_both(self):
        from cost_estimator import estimate_cost_usd
        usage_by_model = {
            "claude-opus-4-8": {
                "input_tokens": 1_000_000,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "claude-sonnet-4-6": {
                "input_tokens": 1_000_000,
                "output_tokens": 0,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        }
        records = _usage_by_model_to_records(usage_by_model)
        usd = estimate_cost_usd(records)
        # opus: $5.00 + sonnet: $3.00 = $8.00
        self.assertAlmostEqual(usd, 8.0, places=6)


def _usage_by_model_to_records(usage_by_model: dict) -> list:
    """Convert usage_by_model dict to a list of records for estimate_cost_usd.

    Each model's summed token counts become one record shaped for the
    cost_estimator.estimate_cost_usd iterable.
    """
    return [
        {
            "model": model,
            "input_tokens": counts.get("input_tokens", 0),
            "output_tokens": counts.get("output_tokens", 0),
            "cache_read_input_tokens": counts.get("cache_read_input_tokens", 0),
            "cache_creation_input_tokens": counts.get("cache_creation_input_tokens", 0),
        }
        for model, counts in usage_by_model.items()
    ]


if __name__ == "__main__":
    unittest.main()

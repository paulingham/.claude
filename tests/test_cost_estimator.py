"""Cost estimator tests (B12.1, ATDD batched-RED).

Public API under test (`hooks/_lib/cost_estimator.py`):
- `estimate_cost_usd(timings: list[dict]) -> float` — sums per-call cost.
- `estimate_cost_usd_per_pipeline(timings_path: str) -> dict[str, float]`
  — reads tool-timings JSONL file and groups by `task_id`.

Pricing source-of-truth (per-million tokens, USD):
- claude-opus-4-7   : input $5,    output $25,  cache_read $0.50
- claude-sonnet-4-6 : input $3,    output $15,  cache_read $0.30
- claude-haiku-4-5-20251001 : input $0.80, output $4, cache_read $0.08

Cache-read tokens are billed at 0.10x of the input rate (anthropic-cache convention).
"""
import json
import math
import os
import tempfile
import unittest
from pathlib import Path

import cost_estimator
from cost_estimator import estimate_cost_usd, estimate_cost_usd_per_pipeline


def _approx_eq(a, b, tol=1e-9):
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


class EstimatesOpusModelDollarMath(unittest.TestCase):
    """AC2: One test per model — Opus."""

    def test_opus_input_and_output_tokens(self):
        # 1,000,000 input @ $5/M + 1,000,000 output @ $25/M = $30
        record = {
            "model": "claude-opus-4-7",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
        }
        usd = estimate_cost_usd([record])
        self.assertTrue(_approx_eq(usd, 30.0), f"got {usd}")

    def test_opus_partial_million_tokens(self):
        # 200,000 input @ $5/M = $1.00 ; 80,000 output @ $25/M = $2.00 → $3.00
        record = {
            "model": "claude-opus-4-7",
            "input_tokens": 200_000,
            "output_tokens": 80_000,
        }
        usd = estimate_cost_usd([record])
        self.assertTrue(_approx_eq(usd, 3.0), f"got {usd}")


class EstimatesSonnetModelDollarMath(unittest.TestCase):
    """AC2: One test per model — Sonnet."""

    def test_sonnet_input_and_output_tokens(self):
        # 1,000,000 input @ $3/M + 1,000,000 output @ $15/M = $18
        record = {
            "model": "claude-sonnet-4-6",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
        }
        usd = estimate_cost_usd([record])
        self.assertTrue(_approx_eq(usd, 18.0), f"got {usd}")


class EstimatesHaikuModelDollarMath(unittest.TestCase):
    """AC2: One test per model — Haiku."""

    def test_haiku_input_and_output_tokens(self):
        # 1,000,000 input @ $0.80/M + 1,000,000 output @ $4/M = $4.80
        record = {
            "model": "claude-haiku-4-5-20251001",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
        }
        usd = estimate_cost_usd([record])
        self.assertTrue(_approx_eq(usd, 4.80), f"got {usd}")


class UnknownModelGracefulFallback(unittest.TestCase):
    """AC2: Unknown-model fallback returns 0.0, no exception."""

    def test_unknown_model_returns_zero_for_that_record(self):
        record = {
            "model": "claude-fake-model-x9",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
        }
        # Must not raise.
        usd = estimate_cost_usd([record])
        self.assertEqual(usd, 0.0)

    def test_unknown_model_does_not_poison_known_records(self):
        # Mixed batch: one unknown + one Opus → only Opus contributes.
        records = [
            {"model": "claude-fake-model-x9",
             "input_tokens": 1_000_000, "output_tokens": 1_000_000},
            {"model": "claude-opus-4-7",
             "input_tokens": 200_000, "output_tokens": 80_000},
        ]
        usd = estimate_cost_usd(records)
        self.assertTrue(_approx_eq(usd, 3.0), f"got {usd}")


class CacheReadTokensBilledAtCheaperRate(unittest.TestCase):
    """AC2: Cache-read pricing differs from regular input."""

    def test_cache_read_tokens_cost_less_than_normal_input(self):
        # 1,000,000 cache_read tokens for Opus
        # Cache-read rate = 0.10 * input_rate = 0.10 * $5/M = $0.50/M
        # So 1M cache-read tokens = $0.50
        cache_only = {
            "model": "claude-opus-4-7",
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 1_000_000,
        }
        normal_only = {
            "model": "claude-opus-4-7",
            "input_tokens": 1_000_000,
            "output_tokens": 0,
        }
        cache_usd = estimate_cost_usd([cache_only])
        normal_usd = estimate_cost_usd([normal_only])
        self.assertTrue(_approx_eq(cache_usd, 0.50), f"got {cache_usd}")
        self.assertTrue(_approx_eq(normal_usd, 5.0), f"got {normal_usd}")
        # Cache-read is cheaper.
        self.assertLess(cache_usd, normal_usd)

    def test_cache_creation_billed_at_input_rate(self):
        # cache_creation_input_tokens are billed at the regular input rate
        # (cache writes cost the same as a fresh input token; cache reads are cheap).
        record = {
            "model": "claude-opus-4-7",
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_input_tokens": 1_000_000,
        }
        usd = estimate_cost_usd([record])
        self.assertTrue(_approx_eq(usd, 5.0), f"got {usd}")

    def test_cache_creation_tokens_bill_at_input_rate_characterization(self):
        """Slice A AC-A7 — characterization test for already-shipped behaviour.

        Pins `_record_cost_usd` cache_creation path at the input rate against
        fixtures. NO source change to `_lib/cost_estimator.py` — this test
        adds coverage of existing logic only. If `_record_cost_usd` ever
        regresses cache_creation to a different rate, this test catches it.

        Mixed-token fixture: regular input + cache_creation + cache_read +
        output. Cost = (input + cache_create) * 5/M + output * 25/M
        + cache_read * 0.5/M.
        """
        record = {
            "model": "claude-opus-4-7",
            "input_tokens": 100_000,           # 100K * $5/M = $0.50
            "output_tokens": 50_000,           #  50K * $25/M = $1.25
            "cache_creation_input_tokens": 200_000,  # 200K * $5/M = $1.00
            "cache_read_input_tokens": 1_000_000,    # 1M * $0.50/M = $0.50
        }
        usd = estimate_cost_usd([record])
        # Total: 0.50 + 1.25 + 1.00 + 0.50 = $3.25
        self.assertTrue(_approx_eq(usd, 3.25), f"got {usd}")
        # Cross-check: 1M cache_creation tokens alone at Opus should equal
        # 1M input tokens alone — same rate.
        creation_only = estimate_cost_usd([{
            "model": "claude-opus-4-7",
            "cache_creation_input_tokens": 1_000_000,
        }])
        input_only = estimate_cost_usd([{
            "model": "claude-opus-4-7",
            "input_tokens": 1_000_000,
        }])
        self.assertTrue(_approx_eq(creation_only, input_only),
                        f"cache_creation ({creation_only}) must equal "
                        f"input rate ({input_only}) per Anthropic prompt-cache "
                        f"convention")


class EstimateCostPerPipelineAggregation(unittest.TestCase):
    """AC2: estimate_cost_usd_per_pipeline groups records by task_id."""

    def test_groups_by_task_id_across_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tool-timings.jsonl"
            records = [
                {"task_id": "alpha", "model": "claude-opus-4-7",
                 "input_tokens": 1_000_000, "output_tokens": 0},  # $5
                {"task_id": "alpha", "model": "claude-sonnet-4-6",
                 "input_tokens": 1_000_000, "output_tokens": 0},  # $3
                {"task_id": "beta", "model": "claude-haiku-4-5-20251001",
                 "input_tokens": 1_000_000, "output_tokens": 1_000_000},  # $4.80
            ]
            with open(path, "w") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")

            result = estimate_cost_usd_per_pipeline(str(path))
            self.assertIn("alpha", result)
            self.assertIn("beta", result)
            self.assertTrue(_approx_eq(result["alpha"], 8.0), f"got {result['alpha']}")
            self.assertTrue(_approx_eq(result["beta"], 4.80), f"got {result['beta']}")

    def test_records_without_task_id_are_skipped(self):
        # Records lacking task_id can't be attributed to a pipeline; they're skipped
        # in the per-pipeline view (still summed in estimate_cost_usd directly).
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tool-timings.jsonl"
            records = [
                {"task_id": "alpha", "model": "claude-opus-4-7",
                 "input_tokens": 1_000_000, "output_tokens": 0},  # $5
                {"model": "claude-opus-4-7",
                 "input_tokens": 1_000_000, "output_tokens": 0},  # no task_id
            ]
            with open(path, "w") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
            result = estimate_cost_usd_per_pipeline(str(path))
            self.assertEqual(set(result.keys()), {"alpha"})
            self.assertTrue(_approx_eq(result["alpha"], 5.0))

    def test_missing_file_returns_empty_dict(self):
        # Graceful: a missing tool-timings.jsonl returns {} not an exception.
        result = estimate_cost_usd_per_pipeline("/nonexistent/path/to/timings.jsonl")
        self.assertEqual(result, {})


class PricingTableSourceOfTruth(unittest.TestCase):
    """AC6: Pricing rates live in a single dict at module top with citation."""

    def test_pricing_table_is_a_module_attribute(self):
        # The module must expose a single pricing dict (DRY: no duplicates).
        self.assertTrue(hasattr(cost_estimator, "PRICING_PER_MILLION"),
                        "expected PRICING_PER_MILLION constant in cost_estimator")
        prices = cost_estimator.PRICING_PER_MILLION
        for model in ("claude-opus-4-7", "claude-sonnet-4-6",
                      "claude-haiku-4-5-20251001"):
            self.assertIn(model, prices, f"missing {model} in pricing table")

    def test_pricing_source_documented_in_module_docstring(self):
        # AC6: future updaters need a citation/URL to verify drift.
        doc = (cost_estimator.__doc__ or "")
        self.assertTrue(
            "pricing" in doc.lower() or "rate" in doc.lower(),
            "module docstring must reference pricing source-of-truth",
        )


class Opus48PricingAndFamilyFallback(unittest.TestCase):
    """T0-a..T0-d: opus-4-8 explicit entry + family-prefix fallback."""

    # Fixed token vector shared across price-equality assertions.
    _TOKENS = {
        "input_tokens": 200_000,
        "output_tokens": 80_000,
        "cache_read_input_tokens": 100_000,
    }

    def _cost(self, model_id):
        return estimate_cost_usd([{"model": model_id, **self._TOKENS}])

    def test_opus_4_8_priced_identically_to_opus_4_7(self):
        # T0-a: claude-opus-4-8 must produce the same non-zero cost as opus-4-7
        # on an identical token vector. $0 means the unknown-model fallback fired.
        cost_4_7 = self._cost("claude-opus-4-7")
        cost_4_8 = self._cost("claude-opus-4-8")
        self.assertGreater(cost_4_8, 0.0,
                           "claude-opus-4-8 billed $0 — missing from PRICING_PER_MILLION")
        self.assertEqual(cost_4_8, cost_4_7,
                         f"opus-4-8 ({cost_4_8}) != opus-4-7 ({cost_4_7})")

    def test_family_prefix_fallback_prices_unknown_opus_bump(self):
        # T0-b: a future model id with no exact PRICING_PER_MILLION entry but a
        # recognised opus- prefix must resolve to a non-zero opus-family price.
        future_model = "claude-opus-4-9-20991231"
        cost_future = self._cost(future_model)
        cost_base = self._cost("claude-opus-4-8")
        self.assertGreater(cost_future, 0.0,
                           f"{future_model} billed $0 — family-prefix fallback missing")
        self.assertEqual(cost_future, cost_base,
                         f"family-fallback price ({cost_future}) != opus base ({cost_base})")

    def test_genuinely_unknown_model_still_returns_zero(self):
        # T0-c: regression — claude-fake-model-x9 has no known family stem;
        # the prefix fallback must NOT match it; existing $0 behaviour preserved.
        usd = self._cost("claude-fake-model-x9")
        self.assertEqual(usd, 0.0,
                         "claude-fake-model-x9 must bill $0 — no matching family stem")

    def test_existing_exact_keys_prices_unchanged(self):
        # T0-d: regression — exact-key lookup must shadow the prefix path;
        # known models must produce their pre-existing prices.
        # Expected values: 200K*input/M + 80K*output/M + 100K*cache_read/M
        cases = {
            "claude-opus-4-7":         3.05,   # 1+2+0.05
            "claude-sonnet-4-6":       1.83,   # 0.6+1.2+0.03
            "claude-haiku-4-5-20251001": 0.488, # 0.16+0.32+0.008
        }
        for model_id, expected in cases.items():
            with self.subTest(model=model_id):
                got = self._cost(model_id)
                self.assertTrue(
                    _approx_eq(got, expected),
                    f"{model_id}: expected {expected}, got {got}",
                )


if __name__ == "__main__":
    unittest.main()

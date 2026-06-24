"""ATDD tests — estimate_cost_usd_for_run (AC2 per-run USD, no parallel pricing path).

AC2: per-arm USD keyed by eval_run_id; reuses PRICING_PER_MILLION SSOT;
     zero matching records → sentinel (not $0.00 float).

test_no_parallel_pricing_path: inspects cost_estimator.py source to confirm
    there is only ONE pricing dict (PRICING_PER_MILLION); no second dict
    created for eval use.
"""
import json
import math
import tempfile
import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
COST_ESTIMATOR_PY = REPO_ROOT / "hooks" / "_lib" / "cost_estimator.py"

# conftest.py adds hooks/_lib to sys.path already
import cost_estimator


def _approx_eq(a, b, tol=1e-9):
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


class AC2PerArmUsdKeyedByEvalRunId(unittest.TestCase):
    """estimate_cost_usd_for_run(run_id, costs_path) filters by eval_run_id."""

    def _write_costs_jsonl(self, tmp_dir, records):
        path = Path(tmp_dir) / "costs.jsonl"
        with open(path, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        return str(path)

    def test_per_arm_usd_keyed_by_eval_run_id_not_task_id(self):
        """Records with different eval_run_id must be attributed separately."""
        from cost_estimator import estimate_cost_usd_for_run
        with tempfile.TemporaryDirectory() as tmp:
            # Two eval runs in the same costs.jsonl
            records = [
                {
                    "eval_run_id": "run-arm-a",
                    "task_id": "some-task",
                    "usage_by_model": {
                        "claude-opus-4-8": {
                            "input_tokens": 1_000_000,
                            "output_tokens": 0,
                            "cache_read_input_tokens": 0,
                            "cache_creation_input_tokens": 0,
                        }
                    },
                },
                {
                    "eval_run_id": "run-arm-b",
                    "task_id": "some-task",
                    "usage_by_model": {
                        "claude-sonnet-4-6": {
                            "input_tokens": 1_000_000,
                            "output_tokens": 0,
                            "cache_read_input_tokens": 0,
                            "cache_creation_input_tokens": 0,
                        }
                    },
                },
            ]
            path = self._write_costs_jsonl(tmp, records)
            usd_a = estimate_cost_usd_for_run("run-arm-a", path)
            usd_b = estimate_cost_usd_for_run("run-arm-b", path)
            # opus-4-8: $5/M input = $5.00
            self.assertTrue(_approx_eq(usd_a, 5.0), f"arm-a got {usd_a}")
            # sonnet-4-6: $3/M input = $3.00
            self.assertTrue(_approx_eq(usd_b, 3.0), f"arm-b got {usd_b}")

    def test_estimate_cost_for_run_reuses_pricing_ssot(self):
        """estimate_cost_usd_for_run must produce results consistent with
        PRICING_PER_MILLION — i.e. it delegates to _record_cost_usd, not
        a second copy of the pricing logic."""
        from cost_estimator import estimate_cost_usd_for_run, PRICING_PER_MILLION, estimate_cost_usd
        with tempfile.TemporaryDirectory() as tmp:
            records = [
                {
                    "eval_run_id": "run-x",
                    "usage_by_model": {
                        "claude-opus-4-8": {
                            "input_tokens": 200_000,
                            "output_tokens": 80_000,
                            "cache_read_input_tokens": 100_000,
                            "cache_creation_input_tokens": 0,
                        }
                    },
                }
            ]
            path = self._write_costs_jsonl(tmp, records)
            per_run_usd = estimate_cost_usd_for_run("run-x", path)
            # Replicate what _record_cost_usd would compute directly
            direct_record = {
                "model": "claude-opus-4-8",
                "input_tokens": 200_000,
                "output_tokens": 80_000,
                "cache_read_input_tokens": 100_000,
                "cache_creation_input_tokens": 0,
            }
            direct_usd = estimate_cost_usd([direct_record])
            self.assertTrue(
                _approx_eq(per_run_usd, direct_usd),
                f"per-run USD ({per_run_usd}) must match direct estimate ({direct_usd}); "
                "pricing path must be shared (SSOT)")

    def test_zero_matching_records_returns_sentinel_not_zero(self):
        """When no records match eval_run_id, return sentinel (not $0.00)."""
        from cost_estimator import estimate_cost_usd_for_run, USD_UNAVAILABLE_SENTINEL
        with tempfile.TemporaryDirectory() as tmp:
            records = [
                {
                    "eval_run_id": "different-run",
                    "usage_by_model": {
                        "claude-opus-4-8": {
                            "input_tokens": 1_000_000,
                        }
                    },
                }
            ]
            path = self._write_costs_jsonl(tmp, records)
            result = estimate_cost_usd_for_run("run-not-present", path)
            # Must return the sentinel, not $0.00
            self.assertIs(result, USD_UNAVAILABLE_SENTINEL,
                          "zero matching records must return USD_UNAVAILABLE_SENTINEL, not $0.00")


class AC2NoPricingPathParallelism(unittest.TestCase):
    """test_no_parallel_pricing_path: source must have exactly one pricing dict."""

    def test_no_parallel_pricing_path(self):
        source = COST_ESTIMATOR_PY.read_text()
        # Count occurrences of dict literals that look like pricing tables
        # (keys: "input", "output", "cache_read" together)
        pricing_dict_pattern = r'["\']input["\']\s*:\s*[\d.]'
        matches = list(__import__("re").finditer(pricing_dict_pattern, source))
        # All matches must be inside the single PRICING_PER_MILLION dict
        # (there should be exactly 4 entries × 1 dict = 4 matches max)
        self.assertLessEqual(
            len(matches), 8,  # 4 models * up to 2 hits per entry (reasonable ceiling)
            "cost_estimator.py must not have a second pricing dict for eval; "
            "PRICING_PER_MILLION is the only SSOT"
        )
        # Confirm PRICING_PER_MILLION is the name
        self.assertIn("PRICING_PER_MILLION", source,
                      "PRICING_PER_MILLION must be the single pricing dict name")
        # Confirm there is NO second dict named differently with pricing content
        # by checking that no other variable name precedes the input pricing pattern
        other_dict_pattern = __import__("re").compile(
            r"(\w+)\s*=\s*\{[^}]*[\"']input[\"']\s*:\s*[\d.]+", __import__("re").DOTALL)
        all_dicts = [m.group(1) for m in other_dict_pattern.finditer(source)]
        pricing_dicts = [d for d in all_dicts if d != "PRICING_PER_MILLION"
                         and not d.startswith("_")]
        self.assertEqual(
            pricing_dicts, [],
            f"unexpected second pricing dict(s): {pricing_dicts}; "
            "PRICING_PER_MILLION must be the only SSOT"
        )

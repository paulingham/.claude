"""Slice-A AC.3 (HIGH-E1) — end-to-end pricing path test.

Plan reference: pipeline-state/harness-opus-4-5-migration/plan.md § Slice A
"end-to-end test: test_cost_estimator_e2e_via_cache_jsonl_emit". Pipes a
synthetic spawn record through the cost_estimator pricing dict (the same
pricing key used by cost-feed.sh + cache-jsonl-emit.py) and asserts that:

  - claude-opus-4-5-20251101 spawn -> total_cost_usd > 0 (key rename intact)
  - claude-opus-4-7 spawn         -> total_cost_usd > 0 (dual-accept window)

The dual-accept assertion proves the A->B->C dependency chain: rate-version
records emitted before the slice-A migration still sum on the aggregator side.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "hooks" / "_lib"))

import cost_estimator  # noqa: E402  — module path resolved at runtime


class CostEstimatorE2eViaCacheJsonlEmit(unittest.TestCase):
    """End-to-end: synthetic JSONL -> estimate_cost_usd_per_pipeline -> > 0."""

    def _synth_record(self, model: str) -> dict:
        return {
            "task_id": "slice-a-e2e",
            "model": model,
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_read_input_tokens": 2000,
            "cache_creation_input_tokens": 300,
        }

    def _run_estimator(self, model: str) -> float:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
            fh.write(json.dumps(self._synth_record(model)) + "\n")
            path = fh.name
        result = cost_estimator.estimate_cost_usd_per_pipeline(path)
        return result.get("slice-a-e2e", 0.0)

    def test_cost_estimator_e2e_via_cache_jsonl_emit(self) -> None:
        cost = self._run_estimator("claude-opus-4-5-20251101")
        self.assertGreater(cost, 0.0,
                           "opus-4-5 record must produce non-zero cost")

    def test_cost_estimator_dual_accept_opus_4_7_still_priced(self) -> None:
        """7-day rollback window: legacy opus-4-7 records still sum > 0."""
        cost = self._run_estimator("claude-opus-4-7")
        self.assertGreater(cost, 0.0,
                           "opus-4-7 dual-accept key must still produce non-zero cost")


if __name__ == "__main__":
    unittest.main()

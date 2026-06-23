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
        # Total approx $0.775
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


class CostReportTaskIdAttribution(unittest.TestCase):
    """Finding 3 — records shaped as cost-tracker.sh now emits: task_id present, no agent_role.

    AC: (a) real task_id attributes to that pipeline bucket;
        (b) task_id "none" buckets as "unattributed" (not as "none");
        (c) no per-agent-role breakdown is derivable (agent_role absent).
    """

    def _step2_aggregate(self, records):
        """Run the Step 2 keying logic from SKILL.md in-process.

        WHY: task_id "none" is the sentinel emitted by cost-tracker.sh when no
        pipeline is active. Treat it as unattributed, same as absent task_id.
        """
        from cost_estimator import estimate_cost_usd
        by_pipeline = {}
        for rec in records:
            if rec.get("event") != "session_end":
                continue
            _tid = rec.get("task_id")
            task_id = _tid if (_tid and _tid != "none") else rec.get("session_id", "unattributed")
            ubm = rec.get("usage_by_model") or {}
            usd = estimate_cost_usd(_usage_by_model_to_records(ubm))
            by_pipeline[task_id] = by_pipeline.get(task_id, 0.0) + usd
        return by_pipeline

    def test_real_task_id_attributes_to_pipeline(self):
        """AC(a): record with a real task_id appears under that task_id bucket."""
        rec = {
            "event": "session_end",
            "task_id": "my-pipeline-123",
            "usage_by_model": {
                "claude-opus-4-8": {
                    "input_tokens": 100_000,
                    "output_tokens": 10_000,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            },
        }
        by_pipeline = self._step2_aggregate([rec])
        self.assertIn("my-pipeline-123", by_pipeline)
        self.assertGreater(by_pipeline["my-pipeline-123"], 0.0)

    def test_task_id_none_buckets_as_unattributed(self):
        """AC(b): record with task_id="none" is treated as unattributed, falls back to session_id."""
        rec = {
            "event": "session_end",
            "task_id": "none",
            "session_id": "sess-abc",
            "usage_by_model": {
                "claude-sonnet-4-6": {
                    "input_tokens": 50_000,
                    "output_tokens": 5_000,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            },
        }
        by_pipeline = self._step2_aggregate([rec])
        # "none" must NOT be a pipeline key -- falls back to session_id
        self.assertNotIn("none", by_pipeline)
        self.assertIn("sess-abc", by_pipeline)

    def test_no_agent_role_in_record_means_no_named_agent_breakdown(self):
        """AC(c): record has no agent_role -- Step 4 grouping yields only "unattributed"."""
        rec = {
            "event": "session_end",
            "task_id": "my-pipeline-123",
            # Deliberately no "agent_role" field -- this is the cost-tracker.sh shape
            "usage_by_model": {
                "claude-opus-4-8": {
                    "input_tokens": 1_000,
                    "output_tokens": 100,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                }
            },
        }
        from cost_estimator import estimate_cost_usd
        # Step 4 grouping: agent_role absent means bucket falls to "unattributed"
        by_agent = {}
        if rec.get("event") == "session_end":
            role = rec.get("agent_role", "unattributed")
            ubm = rec.get("usage_by_model") or {}
            usd = estimate_cost_usd(_usage_by_model_to_records(ubm))
            by_agent[role] = by_agent.get(role, 0.0) + usd
        # No named role -- only "unattributed" is present
        self.assertNotIn("architect", by_agent)
        self.assertNotIn("software-engineer", by_agent)
        self.assertNotIn("code-reviewer", by_agent)
        self.assertIn("unattributed", by_agent)

    def test_skill_md_step4_does_not_claim_per_agent_usd(self):
        """AC(c) doc-shape: SKILL.md must NOT contain fabricated agent-role cost rows."""
        doc = (REPO_ROOT / "skills" / "cost-report" / "SKILL.md").read_text()
        self.assertNotIn("$74.10", doc, "fabricated architect cost row must be removed")
        self.assertNotIn("$58.32", doc, "fabricated software-engineer cost row must be removed")
        self.assertNotIn("$22.04", doc, "fabricated code-reviewer cost row must be removed")

    def test_cost_tracker_record_has_task_id_field(self):
        """AC(a) doc-shape: SKILL.md Step 2 references task_id keying for costs.jsonl records."""
        doc = (REPO_ROOT / "skills" / "cost-report" / "SKILL.md").read_text()
        self.assertIn("task_id", doc, "SKILL.md Step 2 must reference task_id keying")


def _usage_by_model_to_records(usage_by_model: dict) -> list:
    """Convert usage_by_model dict to a list of records for estimate_cost_usd.

    Each model\'s summed token counts become one record shaped for the
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

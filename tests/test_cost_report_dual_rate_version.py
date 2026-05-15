"""Slice-A AC.3 MED-rate_version-rollback — dual-accept window for /cost-report.

Plan reference: pipeline-state/harness-opus-4-5-migration/plan.md § Slice A
files-to-change: skills/cost-report/SKILL.md - accept both `opus-4-7-2026-04`
and `opus-4-5-2026-05` rate_version tokens for a 7-day window post-merge.

The test asserts the SKILL.md doc declares the dual-accept policy. It does
NOT (in this slice) assert behaviour on a live aggregator — that requires a
runnable aggregator binary; for now the SKILL is consumed by an LLM agent and
the doc is the contract.
"""
from __future__ import annotations

import pathlib
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SKILL = _REPO_ROOT / "skills" / "cost-report" / "SKILL.md"


class AggregatorAcceptsBothTokensDuringWindow(unittest.TestCase):
    """The cost-report aggregator accepts both rate_version tokens for 7 days."""

    def test_aggregator_accepts_both_tokens_during_window(self) -> None:
        text = _SKILL.read_text(encoding="utf-8")
        # Both tokens must be named so the agent driving the aggregator knows
        # to sum them as one population during the window.
        self.assertIn("opus-4-7-2026-04", text,
                      "SKILL.md must name the legacy rate_version token")
        self.assertIn("opus-4-5-2026-05", text,
                      "SKILL.md must name the post-migration rate_version token")
        # The dual-accept policy + 7-day window must be documented.
        self.assertIn("dual-accept", text.lower(),
                      "SKILL.md must declare a dual-accept policy")
        self.assertIn("7-day", text,
                      "SKILL.md must declare the 7-day window")


if __name__ == "__main__":
    unittest.main()

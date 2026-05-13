"""AC5 — `skills/cost-report/SKILL.md` emits `## Sandbox Verify Skip Rate`.

The skill file documents an additional section (Step 5) that renders the
skip-rate aggregate. These tests assert the skill file itself documents
the section + uses the shared `sandbox_skip_rate.aggregate_skip_rate`
helper.

This is a doc-shape test (mirroring the schema-doc tests) — the skill
text IS the contract; the actual rendering happens at invocation time
in the orchestrator's runtime path. Future Story 5 (out of scope) may
add an integration test that runs the skill end-to-end.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class CostReportEmitsSandboxSkipRateSection(unittest.TestCase):
    """`skills/cost-report/SKILL.md` Step 5 documents the new section."""

    def test_skill_documents_sandbox_skip_rate_section(self):
        doc = (REPO_ROOT / "skills" / "cost-report" / "SKILL.md").read_text()
        self.assertIn(
            "Sandbox Verify Skip Rate",
            doc,
            "cost-report skill must document the `## Sandbox Verify "
            "Skip Rate` section")

    def test_skill_references_aggregator_helper(self):
        doc = (REPO_ROOT / "skills" / "cost-report" / "SKILL.md").read_text()
        self.assertIn(
            "sandbox_skip_rate",
            doc,
            "cost-report skill must reference the aggregator helper "
            "by name so the wiring is discoverable")


class CostReportSandboxSectionAbsentWhenNoData(unittest.TestCase):
    """Helper returns zeroes on empty metrics_root — section header
    is documented as either rendered with zeros OR omitted entirely.

    Either behaviour is acceptable; the test simply confirms the helper
    does not raise. The skill text documents the choice.
    """

    def test_helper_does_not_raise_on_empty(self):
        import sys
        sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))
        import sandbox_skip_rate
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # Empty metrics root.
            result = sandbox_skip_rate.aggregate_skip_rate(Path(tmp))
            self.assertEqual(result["total_invocations"], 0)
            self.assertEqual(result["reasons"], {})


if __name__ == "__main__":
    unittest.main()

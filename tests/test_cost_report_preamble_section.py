"""AC tests — `skills/cost-report/SKILL.md` emits `## Preamble Tokens (MEASURED)`.

The skill file documents an additional section that renders the
per-session measured preamble token aggregate. These tests assert the
skill file itself documents the section + uses the shared
`preamble_tokens_aggregate.aggregate_preamble_tokens` helper.

This is a doc-shape test (mirroring the schema-doc tests) — the skill
text IS the contract; the actual rendering happens at invocation time
in the orchestrator's runtime path.
"""
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class CostReportEmitsPreambleTokensSection(unittest.TestCase):
    """`skills/cost-report/SKILL.md` documents the Preamble Tokens section."""

    def test_skill_documents_preamble_tokens_measured_section(self):
        doc = (REPO_ROOT / "skills" / "cost-report" / "SKILL.md").read_text()
        self.assertIn(
            "Preamble Tokens (MEASURED)",
            doc,
            "cost-report skill must document the `## Preamble Tokens (MEASURED)` "
            "section")

    def test_skill_references_preamble_aggregator_helper(self):
        doc = (REPO_ROOT / "skills" / "cost-report" / "SKILL.md").read_text()
        self.assertIn(
            "preamble_tokens_aggregate",
            doc,
            "cost-report skill must reference the aggregator helper "
            "by name so the wiring is discoverable")


class CostReportPreambleSectionEmptyState(unittest.TestCase):
    """Helper returns zeroes on empty metrics_root — never raises."""

    def test_helper_does_not_raise_on_empty(self):
        import sys
        sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))
        import preamble_tokens_aggregate
        with tempfile.TemporaryDirectory() as tmp:
            result = preamble_tokens_aggregate.aggregate_preamble_tokens(Path(tmp))
            self.assertEqual(result["total_preamble_tokens"], 0)
            self.assertEqual(result["session_count"], 0)


class CostReportPreambleSectionNonZeroData(unittest.TestCase):
    """AC2 core — fixture with a real session_end record produces correct totals."""

    def test_preamble_tokens_summed_from_session_end_records(self):
        import sys
        sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))
        import preamble_tokens_aggregate
        with tempfile.TemporaryDirectory() as tmp:
            costs_file = Path(tmp) / "costs.jsonl"
            # Valid session_end record with preamble_tokens
            valid = json.dumps({
                "event": "session_end",
                "session_id": "abc123",
                "preamble_tokens": 4321,
            })
            # Non-session_end noise line (must be ignored)
            noise = json.dumps({
                "event": "tool_use",
                "session_id": "abc123",
                "preamble_tokens": 9999,
            })
            # Malformed line (dropped_lines should count it)
            malformed = "NOT VALID JSON {"
            costs_file.write_text("\n".join([valid, noise, malformed]) + "\n")

            result = preamble_tokens_aggregate.aggregate_preamble_tokens(Path(tmp))

        self.assertEqual(result["total_preamble_tokens"], 4321)
        self.assertEqual(result["session_count"], 1)
        self.assertEqual(result["dropped_lines"], 1)


if __name__ == "__main__":
    unittest.main()

"""AC tests — `skills/cost-report/SKILL.md` emits `## Preamble Tokens (estimated, bytes/3.5)`.

The skill file documents an additional section that renders the
per-session estimated preamble token aggregate. These tests assert the
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

    def test_skill_documents_preamble_tokens_estimated_section(self):
        doc = (REPO_ROOT / "skills" / "cost-report" / "SKILL.md").read_text()
        self.assertIn(
            "Preamble Tokens (estimated, bytes/3.5)",
            doc,
            "cost-report skill must document the `## Preamble Tokens (estimated, bytes/3.5)` "
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


class CostReportPreambleDroppedLinesContract(unittest.TestCase):
    """Lock in the corrected dropped_lines contract (FIX 1 + FIX 2 regression tests)."""

    def _run(self, lines):
        import sys
        sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))
        import preamble_tokens_aggregate
        with tempfile.TemporaryDirectory() as tmp:
            costs_file = Path(tmp) / "costs.jsonl"
            costs_file.write_text("\n".join(json.dumps(r) if isinstance(r, dict) else r
                                            for r in lines) + "\n")
            return preamble_tokens_aggregate.aggregate_preamble_tokens(Path(tmp))

    def test_negative_preamble_tokens_counted_as_dropped(self):
        result = self._run([{"event": "session_end", "preamble_tokens": -1}])
        self.assertEqual(result["dropped_lines"], 1)
        self.assertEqual(result["session_count"], 0)
        self.assertEqual(result["total_preamble_tokens"], 0)

    def test_string_preamble_tokens_counted_as_dropped(self):
        result = self._run([{"event": "session_end", "preamble_tokens": "1234"}])
        self.assertEqual(result["dropped_lines"], 1)
        self.assertEqual(result["session_count"], 0)

    def test_absent_preamble_tokens_counted_as_dropped(self):
        result = self._run([{"event": "session_end", "session_id": "x"}])
        self.assertEqual(result["dropped_lines"], 1)
        self.assertEqual(result["session_count"], 0)

    def test_bool_preamble_tokens_counted_as_dropped(self):
        result = self._run([{"event": "session_end", "preamble_tokens": True}])
        self.assertEqual(result["dropped_lines"], 1)
        self.assertEqual(result["session_count"], 0)
        self.assertEqual(result["total_preamble_tokens"], 0)

    def test_non_session_end_with_preamble_tokens_silently_skipped(self):
        result = self._run([{"event": "tool_use", "preamble_tokens": 9999}])
        self.assertEqual(result["dropped_lines"], 0)
        self.assertEqual(result["session_count"], 0)
        self.assertEqual(result["total_preamble_tokens"], 0)

    def test_happy_path_4321_unchanged(self):
        result = self._run([{"event": "session_end", "preamble_tokens": 4321}])
        self.assertEqual(result["total_preamble_tokens"], 4321)
        self.assertEqual(result["session_count"], 1)
        self.assertEqual(result["dropped_lines"], 0)

    def test_mixed_fixture_identity_invariant(self):
        lines = [
            # 1 valid session_end
            {"event": "session_end", "preamble_tokens": 1000},
            # 3 corrupt session_end records
            {"event": "session_end", "preamble_tokens": -5},
            {"event": "session_end", "preamble_tokens": "bad"},
            {"event": "session_end"},
            # 1 non-session_end noise line with preamble_tokens (skip, not dropped)
            {"event": "tool_use", "preamble_tokens": 500},
            # 1 malformed JSON line
            "NOT VALID JSON {",
        ]
        result = self._run(lines)
        self.assertEqual(result["total_preamble_tokens"], 1000)
        self.assertEqual(result["session_count"], 1)
        self.assertEqual(result["dropped_lines"], 4)  # 3 corrupt + 1 malformed JSON


if __name__ == "__main__":
    unittest.main()

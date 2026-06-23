"""AC1: triggered_by_pipeline_id optional field documented in observation schema.

Verifies:
- protocols/autonomous-intelligence.md § Observation Capture documents a
  triggered_by_pipeline_id field (root-level, OPTIONAL, sister to classification).
- The field appears in the pipeline-record example JSON at the same brace-depth
  as classification (not nested under phases).
- A verbatim absence-tolerance clause is present:
  "NEVER coerced to a synthetic/guessed link" AND
  "not a tracked post-merge regression".
- The field-reference row documents the field as OR absent / OPTIONAL.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "protocols" / "autonomous-intelligence.md"


def _observation_capture_section() -> str:
    """Return the body of `### Observation Capture` up to the next `### `/`## `."""
    text = DOC.read_text()
    match = re.search(
        r"###\s+Observation Capture\b(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


class TriggeredByPipelineIdFieldDocumented(unittest.TestCase):
    def test_field_documented_in_observation_capture(self):
        """Windowed § Observation Capture body must contain triggered_by_pipeline_id."""
        body = _observation_capture_section()
        self.assertTrue(body, "§ Observation Capture not found in autonomous-intelligence.md")
        self.assertIn(
            "triggered_by_pipeline_id",
            body,
            "§ Observation Capture must document the triggered_by_pipeline_id field "
            "(root-level OPTIONAL field on the pipeline record)",
        )

    def test_field_is_root_level_sister_to_classification(self):
        """Example JSON must have triggered_by_pipeline_id at the same brace-depth as classification."""
        body = _observation_capture_section()
        self.assertTrue(body, "§ Observation Capture not found")
        # Extract the pipeline-record fenced block (the first bash/json block with record_type:pipeline)
        match = re.search(
            r"```(?:bash|json)?\n(.*?\"record_type\":\s*\"pipeline\".*?)\n```",
            body, re.DOTALL)
        self.assertIsNotNone(
            match,
            "A fenced block with \"record_type\": \"pipeline\" must exist in § Observation Capture",
        )
        block = match.group(1)
        self.assertIn(
            "triggered_by_pipeline_id",
            block,
            "The pipeline-record example JSON must include triggered_by_pipeline_id",
        )
        # Both classification and triggered_by_pipeline_id must NOT be inside a nested block
        # (i.e., they should not be indented more than classification).
        # Verify both appear at the same level: find the indentation of "classification" line
        # and assert triggered_by_pipeline_id has the same indentation (root-level, not in phases).
        classification_match = re.search(r'^(\s*)"classification"', block, re.MULTILINE)
        triggered_match = re.search(r'^(\s*)"triggered_by_pipeline_id"', block, re.MULTILINE)
        self.assertIsNotNone(
            classification_match,
            "pipeline-record block must contain classification",
        )
        self.assertIsNotNone(
            triggered_match,
            "pipeline-record block must contain triggered_by_pipeline_id at root level",
        )
        self.assertEqual(
            classification_match.group(1),
            triggered_match.group(1),
            "triggered_by_pipeline_id must be at the same indentation depth as classification "
            "(root-level, not nested under phases)",
        )

    def test_absence_tolerance_clause_verbatim(self):
        """Verbatim backward-compat clause must contain exact required phrases."""
        body = _observation_capture_section()
        self.assertTrue(body, "§ Observation Capture not found")
        self.assertIn(
            "NEVER coerced to a synthetic/guessed link",
            body,
            "backward-compatibility note must include verbatim phrase "
            "'NEVER coerced to a synthetic/guessed link'",
        )
        self.assertIn(
            "not a tracked post-merge regression",
            body,
            "backward-compatibility note must include verbatim phrase "
            "'not a tracked post-merge regression'",
        )

    def test_field_marked_optional_not_required(self):
        """Field-reference row must document the field as OR absent / OPTIONAL."""
        body = _observation_capture_section()
        self.assertTrue(body, "§ Observation Capture not found")
        # Find the triggered_by_pipeline_id row in the field-reference table
        match = re.search(
            r"\|\s*`?triggered_by_pipeline_id`?\s*\|(.+?)(?=\n\||\Z)",
            body)
        self.assertIsNotNone(
            match,
            "Field-reference table must have a row for triggered_by_pipeline_id",
        )
        row = match.group(1)
        self.assertRegex(
            row,
            r"OR\s+absent|OPTIONAL|optional",
            msg="triggered_by_pipeline_id field-reference row must document "
                "the field as 'OR absent' or 'OPTIONAL' (never declared required)",
        )


if __name__ == "__main__":
    unittest.main()

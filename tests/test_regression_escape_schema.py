"""AC1: deploy_outcome record type and outcome field documented in observation schema.

Verifies:
- protocols/autonomous-intelligence.md § Observation Capture documents a
  companion deploy_outcome record type with pipeline_id + outcome field.
- All four outcome enum values are documented:
  DEPLOYED / ROLLED_BACK / AUTO_ROLLBACK / DEPLOY_FAILED.
- An example fenced block with "record_type": "deploy_outcome" is present.
- The backward-compatibility absence-tolerance wording is present using
  verbatim key phrases (absence is never coerced to synthetic clean/success).
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


class DeployOutcomeSchemaDocumented(unittest.TestCase):
    def test_deploy_outcome_record_type_documented(self):
        body = _observation_capture_section()
        self.assertTrue(body, "§ Observation Capture not found")
        self.assertIn("deploy_outcome", body,
                      "§ Observation Capture must document deploy_outcome record type")
        self.assertIn("outcome", body,
                      "§ Observation Capture must document the outcome field name")

    def test_outcome_enum_values_documented(self):
        body = _observation_capture_section()
        self.assertTrue(body, "§ Observation Capture not found")
        for value in ("DEPLOYED", "ROLLED_BACK", "AUTO_ROLLBACK", "DEPLOY_FAILED"):
            self.assertIn(value, body,
                          f"§ Observation Capture must document outcome enum value {value}")

    def test_deploy_outcome_example_block_present(self):
        body = _observation_capture_section()
        self.assertTrue(body, "§ Observation Capture not found")
        match = re.search(
            r"```(?:bash|json)?\n(.*?\"record_type\":\s*\"deploy_outcome\".*?)\n```",
            body, re.DOTALL)
        self.assertIsNotNone(
            match,
            "A fenced block with \"record_type\": \"deploy_outcome\" must exist in "
            "§ Observation Capture")
        block = match.group(1)
        self.assertIn("pipeline_id", block,
                      "deploy_outcome example block must carry pipeline_id field")
        self.assertIn("outcome", block,
                      "deploy_outcome example block must carry outcome field")

    def test_backward_compat_absence_tolerance_verbatim(self):
        body = _observation_capture_section()
        self.assertTrue(body, "§ Observation Capture not found")
        self.assertRegex(
            body,
            r"tolerate\s+absence",
            msg="backward-compatibility note must say readers tolerate absence",
        )
        self.assertIn(
            "NEVER coerced to a synthetic clean/success",
            body,
            "backward-compatibility note must include verbatim phrase "
            "'NEVER coerced to a synthetic clean/success'",
        )


if __name__ == "__main__":
    unittest.main()

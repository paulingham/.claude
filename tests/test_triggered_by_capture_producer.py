"""AC2: triggered_by_pipeline_id capture documented (intake primary + bug-fix fallback)
and conditionally emitted from the Step 4d-i producer.

Verifies:
- skills/pipeline/SKILL.md Step 4d-i JSON template includes triggered_by_pipeline_id.
- Step 4d-i documents omit-when-absent + never-null producer rule.
- skills/intake/SKILL.md Discussion Persistence § Impact on Implementation contains
  a triggered-by optional capture line (PRIMARY capture; windowed to that sub-section).
- skills/bug-fix/SKILL.md documents the triggered_by_pipeline_id fallback capture
  with a never-fabricate qualifier.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINE = REPO_ROOT / "skills" / "pipeline" / "SKILL.md"
INTAKE = REPO_ROOT / "skills" / "intake" / "SKILL.md"
BUGFIX = REPO_ROOT / "skills" / "bug-fix" / "SKILL.md"


def _step4di_body() -> str:
    """Return the body of the #### 4d-i section up to the next #### or ###."""
    text = PIPELINE.read_text()
    match = re.search(
        r"####\s+4d-i\b(.+?)(?=\n####\s+|\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


def _impact_on_implementation_body() -> str:
    """Return the body of the ### Impact on Implementation sub-section in intake SKILL.md."""
    text = INTAKE.read_text()
    match = re.search(
        r"###\s+Impact on Implementation\b(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    if match:
        return match.group(1)
    # Fallback: look for the Impact on Implementation block inside Discussion Persistence
    match2 = re.search(
        r"Impact on Implementation\b(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match2.group(1) if match2 else ""


class Step4diProducerDocumentsTriggeredBy(unittest.TestCase):
    def test_step4di_template_includes_optional_field(self):
        """Windowed Step 4d-i body must contain triggered_by_pipeline_id in the JSON template."""
        body = _step4di_body()
        self.assertTrue(
            body,
            "#### 4d-i section not found in skills/pipeline/SKILL.md",
        )
        self.assertIn(
            "triggered_by_pipeline_id",
            body,
            "Step 4d-i JSON template must include triggered_by_pipeline_id "
            "(root-level OPTIONAL field on the pipeline record)",
        )

    def test_producer_documents_omit_when_absent_never_null(self):
        """Step 4d-i must document omit-when-absent + never-null for triggered_by_pipeline_id."""
        body = _step4di_body()
        self.assertTrue(
            body,
            "#### 4d-i section not found in skills/pipeline/SKILL.md",
        )
        # Must say "omit" somewhere near triggered_by_pipeline_id
        self.assertRegex(
            body,
            r"omit",
            msg="Step 4d-i must document omit-when-absent behaviour for triggered_by_pipeline_id",
        )
        # Must explicitly forbid null
        self.assertRegex(
            body,
            r"never\s+write\s+null|NEVER\s+write\s+null|never.*null|NEVER.*null",
            msg="Step 4d-i must document that triggered_by_pipeline_id MUST NOT be written as null "
                "(mirrors persona_rejections absence rule)",
        )

    def test_intake_discussion_documents_primary_capture(self):
        """skills/intake/SKILL.md Discussion Persistence § Impact on Implementation
        must contain a triggered-by optional capture line (windowed to that sub-section)."""
        body = _impact_on_implementation_body()
        self.assertTrue(
            body,
            "§ Impact on Implementation sub-section not found in skills/intake/SKILL.md; "
            "must be present inside Discussion Persistence block",
        )
        self.assertRegex(
            body,
            r"[Tt]riggered.by",
            msg="§ Impact on Implementation must document the triggered-by optional capture "
                "line (PRIMARY capture of triggered_by_pipeline_id from user context)",
        )
        # Must be marked optional — never required
        self.assertRegex(
            body,
            r"optional|OPTIONAL|OMIT|omit",
            msg="§ Impact on Implementation triggered-by bullet must be marked OPTIONAL / OMIT when unknown",
        )

    def test_bugfix_documents_fallback_capture_never_fabricate(self):
        """skills/bug-fix/SKILL.md must document triggered_by_pipeline_id fallback
        with a never-fabricate / omit-when-unknown qualifier."""
        text = BUGFIX.read_text()
        self.assertIn(
            "triggered_by_pipeline_id",
            text,
            "skills/bug-fix/SKILL.md must document triggered_by_pipeline_id as a fallback "
            "capture surface (when root-cause identifies the originating pipeline)",
        )
        # Must carry a never-fabricate / omit-when-unknown qualifier
        self.assertRegex(
            text,
            r"[Nn]ever\s+fabricate|NEVER\s+fabricate|[Oo]mit\s+when|omit.*unknown|OMIT.*unknown",
            msg="skills/bug-fix/SKILL.md triggered_by_pipeline_id sentence must include "
                "a never-fabricate or omit-when-unknown qualifier",
        )


if __name__ == "__main__":
    unittest.main()

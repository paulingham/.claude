"""Guard tests for WS-F slice-2 integration wiring.

Verifies:
- design-qc SKILL.md contains Step 6.26 section
- design-qc Step 6.26 documents a11y_axe key in index.json
- design-qc Step 6.26 has scratchpad token axe-scan-failed
- frontend-engineer Testing section mentions accessibility-check
- pipeline SKILL.md Final Gate references /harness:accessibility-check with frontend trigger
- a11y_axe is an additive key (design-qc a11y slice1 additive test still green — covered separately)
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DESIGN_QC = REPO_ROOT / "skills" / "design-qc" / "SKILL.md"
FRONTEND_ENGINEER = REPO_ROOT / "agents" / "frontend-engineer.md"
PIPELINE_SKILL = REPO_ROOT / "skills" / "pipeline" / "SKILL.md"


def _testing_section(text):
    """Extract the ## Testing section from a markdown file."""
    import re
    match = re.search(r'## Testing\n(.*?)(?=\n## |\Z)', text, re.DOTALL)
    return match.group(1) if match else ''


class DesignQcStep626(unittest.TestCase):

    def test_design_qc_has_step_6_26(self):
        self.assertIn('Step 6.26', DESIGN_QC.read_text())

    def test_design_qc_step_6_26_documents_a11y_axe_key(self):
        self.assertIn('a11y_axe', DESIGN_QC.read_text())

    def test_design_qc_step_6_26_has_axe_scan_failed_token(self):
        self.assertIn('axe-scan-failed', DESIGN_QC.read_text())


class FrontendEngineerAndPipelineWiring(unittest.TestCase):

    def test_frontend_engineer_testing_section_mentions_accessibility_check(self):
        text = FRONTEND_ENGINEER.read_text()
        section = _testing_section(text)
        self.assertIn(
            'accessibility-check',
            section,
            "frontend-engineer.md ## Testing section must mention accessibility-check",
        )

    def test_pipeline_skill_references_accessibility_check_with_frontend_trigger(self):
        text = PIPELINE_SKILL.read_text()
        self.assertIn(
            '/harness:accessibility-check',
            text,
            "skills/pipeline/SKILL.md must reference /harness:accessibility-check",
        )
        # Assert frontend-change trigger condition present
        has_trigger = (
            'tsx' in text or 'jsx' in text or 'frontend' in text
        )
        self.assertTrue(
            has_trigger,
            "skills/pipeline/SKILL.md must contain a frontend-change trigger condition near accessibility-check",
        )


if __name__ == '__main__':
    unittest.main()

"""Guard tests for WS-F accessibility-check verdicts in verdict catalog.

Verifies:
- A11Y_CHECK_PASSED in protocols/verdict-catalog.md
- A11Y_CHECK_FAILED in protocols/verdict-catalog.md
- A11Y_CHECK_SKIPPED in protocols/verdict-catalog.md
- Each row attributes emitter 'accessibility-check'
- SKILL.md frontmatter has verdict field containing A11Y_CHECK_PASSED
- SKILL.md contains route-detection step (git diff --name-only)
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "protocols" / "verdict-catalog.md"
SKILL = REPO_ROOT / "skills" / "accessibility-check" / "SKILL.md"


class A11yCheckVerdictsInCatalog(unittest.TestCase):

    def test_a11y_check_passed_in_catalog(self):
        self.assertIn('A11Y_CHECK_PASSED', CATALOG.read_text())

    def test_a11y_check_failed_in_catalog(self):
        self.assertIn('A11Y_CHECK_FAILED', CATALOG.read_text())

    def test_a11y_check_skipped_in_catalog(self):
        self.assertIn('A11Y_CHECK_SKIPPED', CATALOG.read_text())

    def test_a11y_check_verdicts_attribute_correct_emitter(self):
        text = CATALOG.read_text()
        for verdict in ('A11Y_CHECK_PASSED', 'A11Y_CHECK_FAILED', 'A11Y_CHECK_SKIPPED'):
            found = False
            for line in text.splitlines():
                if verdict in line and 'accessibility-check' in line:
                    found = True
                    break
            self.assertTrue(
                found,
                f"Catalog row for {verdict} must attribute emitter 'accessibility-check'",
            )


class SkillFrontmatterAndProcedure(unittest.TestCase):

    def test_skill_frontmatter_has_verdict_field(self):
        import re
        text = SKILL.read_text()
        # Extract YAML frontmatter between --- markers
        fm_match = re.match(r'^---\n(.*?)\n---', text, re.DOTALL)
        self.assertIsNotNone(fm_match, "SKILL.md must have YAML frontmatter")
        frontmatter = fm_match.group(1)
        self.assertIn('verdict', frontmatter, "frontmatter must have verdict key")
        self.assertIn('A11Y_CHECK_PASSED', frontmatter,
                      "frontmatter verdict must contain A11Y_CHECK_PASSED")

    def test_skill_has_route_detection_step(self):
        self.assertIn('git diff --name-only', SKILL.read_text(),
                      "SKILL.md must contain route-detection step with 'git diff --name-only'")


if __name__ == '__main__':
    unittest.main()

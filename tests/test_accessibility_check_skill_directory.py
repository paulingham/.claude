"""Guard tests for WS-F accessibility-check row in skill-directory Active Skills table.

Verifies:
- /accessibility-check row present in ## Active Skills section
- Row lists verdict A11Y_CHECK_PASSED and A11Y_CHECK_FAILED
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "protocols" / "skill-directory.md"


def _active_skills_section():
    text = SKILL_DIR.read_text()
    match = re.search(r'## Active Skills\n(.*?)(?=\n## |\Z)', text, re.DOTALL)
    return match.group(1) if match else ''


class AccessibilityCheckSkillListedInActiveTable(unittest.TestCase):

    def test_accessibility_check_skill_listed_in_active_table(self):
        section = _active_skills_section()
        self.assertTrue(
            section,
            "protocols/skill-directory.md must have an '## Active Skills' section",
        )
        row = None
        for line in section.splitlines():
            if 'accessibility-check' in line and line.lstrip().startswith('|'):
                row = line
                break
        self.assertIsNotNone(
            row,
            "protocols/skill-directory.md Active Skills must list `/accessibility-check`",
        )

    def test_accessibility_check_row_lists_correct_verdicts(self):
        section = _active_skills_section()
        row = None
        for line in section.splitlines():
            if 'accessibility-check' in line and line.lstrip().startswith('|'):
                row = line
                break
        self.assertIsNotNone(row, "Must find /accessibility-check row first")
        self.assertIn(
            'A11Y_CHECK_PASSED', row,
            "/accessibility-check row must list A11Y_CHECK_PASSED",
        )
        self.assertIn(
            'A11Y_CHECK_FAILED', row,
            "/accessibility-check row must list A11Y_CHECK_FAILED",
        )


if __name__ == '__main__':
    unittest.main()

"""Slice 9: SKILL.md has real-backend description + POSIX Requirements + truncation."""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SKILL_MD = REPO_ROOT / "skills" / "embedder" / "SKILL.md"


class SkillMarkdownHonesty(unittest.TestCase):
    def test_infrastructure_only_banner_replaced(self):
        text = _SKILL_MD.read_text()
        self.assertNotIn("Current status: infrastructure only", text)
        self.assertNotIn("deferred to Story S5.1", text)

    def test_requirements_section_declares_posix_only(self):
        text = _SKILL_MD.read_text()
        self.assertIn("## Requirements", text)
        self.assertIn("macOS or Linux", text)
        self.assertIn("Windows is not supported", text)

    def test_truncation_paragraph_documents_128_vs_512(self):
        text = _SKILL_MD.read_text()
        self.assertIn("128", text)
        self.assertIn("512", text)
        self.assertIn("Capture", text)
        self.assertIn("Backfill", text)


if __name__ == "__main__":
    unittest.main()

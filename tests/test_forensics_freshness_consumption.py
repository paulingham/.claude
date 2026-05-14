"""Slice 5: skills/forensics/SKILL.md surfaces freshness-guard.jsonl records.

AC5.2: forensics Step 3 (or a new sub-step) must:
  - reference metrics/{session}/freshness-guard.jsonl
  - filter for action='would_block' AND source='path-b-advisory'
  - tag the row as Rule Protected: rules/core.md:Iron Law 2
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FORENSICS = REPO_ROOT / "skills" / "forensics" / "SKILL.md"


class ForensicsFreshnessConsumption(unittest.TestCase):
    def setUp(self):
        self.text = FORENSICS.read_text()

    def test_forensics_skill_md_references_freshness_guard_jsonl(self):
        self.assertIn("freshness-guard.jsonl", self.text,
                      "forensics must reference freshness-guard.jsonl")

    def test_forensics_step_documents_path_b_advisory_filter(self):
        # The filter pair must both appear so operators know what to grep for.
        self.assertIn("would_block", self.text)
        self.assertIn("path-b-advisory", self.text)

    def test_forensics_step_tags_iron_law_2(self):
        # Rule Protected annotation per Step 3b convention.
        self.assertIn("Iron Law 2", self.text)


if __name__ == "__main__":
    unittest.main()

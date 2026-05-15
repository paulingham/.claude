"""B6-AC5/AC6: SE and FE agent frontmatter has Sonnet executor + Opus advisor.

Pins the cost-mapped Wave 5 default. Drift fails CI in either direction.
"""
import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"


def _frontmatter(role):
    text = (AGENTS_DIR / f"{role}.md").read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(match.group(1)) if match else {}


class SeFrontmatterIsSonnet(unittest.TestCase):
    def test_software_engineer_executor_is_sonnet(self):
        fm = _frontmatter("software-engineer")
        self.assertEqual(fm.get("executor"), "claude-sonnet-4-6")
        self.assertEqual(fm.get("advisor"), "claude-opus-4-5-20251101")


class FeFrontmatterIsSonnet(unittest.TestCase):
    def test_frontend_engineer_executor_is_sonnet(self):
        fm = _frontmatter("frontend-engineer")
        self.assertEqual(fm.get("executor"), "claude-sonnet-4-6")
        self.assertEqual(fm.get("advisor"), "claude-opus-4-5-20251101")


if __name__ == "__main__":
    unittest.main()

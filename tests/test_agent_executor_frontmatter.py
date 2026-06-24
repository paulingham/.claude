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
        from model_alias import resolve_model_alias
        fm = _frontmatter("software-engineer")
        self.assertEqual(fm.get("executor"), "mid",
                         "software-engineer executor must be alias 'mid'")
        self.assertEqual(resolve_model_alias(fm.get("executor")), "claude-sonnet-4-6",
                         "alias 'mid' must resolve to claude-sonnet-4-6")
        self.assertEqual(fm.get("advisor"), "strong",
                         "software-engineer advisor must be alias 'strong'")
        self.assertEqual(resolve_model_alias(fm.get("advisor")), "claude-opus-4-8",
                         "alias 'strong' must resolve to claude-opus-4-8")


class FeFrontmatterIsSonnet(unittest.TestCase):
    def test_frontend_engineer_executor_is_sonnet(self):
        from model_alias import resolve_model_alias
        fm = _frontmatter("frontend-engineer")
        self.assertEqual(fm.get("executor"), "mid",
                         "frontend-engineer executor must be alias 'mid'")
        self.assertEqual(resolve_model_alias(fm.get("executor")), "claude-sonnet-4-6",
                         "alias 'mid' must resolve to claude-sonnet-4-6")
        self.assertEqual(fm.get("advisor"), "strong",
                         "frontend-engineer advisor must be alias 'strong'")
        self.assertEqual(resolve_model_alias(fm.get("advisor")), "claude-opus-4-8",
                         "alias 'strong' must resolve to claude-opus-4-8")


if __name__ == "__main__":
    unittest.main()

"""Snapshot test: each agent declares the expected `instinct_categories:`."""
import re
import unittest
from pathlib import Path

import yaml

AGENTS_DIR = Path(__file__).resolve().parents[1] / "agents"

EXPECTED = {
    "software-engineer": [
        "software-engineer", "frontend-engineer", "database-engineer"],
    "frontend-engineer": ["frontend-engineer"],
    "database-engineer": ["database-engineer", "software-engineer"],
    "infrastructure-engineer": ["infrastructure-engineer"],
    "architect": ["architect", "software-engineer", "security-engineer"],
    "code-reviewer": [
        "code-reviewer", "software-engineer",
        "frontend-engineer", "database-engineer"],
    "security-engineer": ["security-engineer"],
    "qa-engineer": ["qa-engineer", "software-engineer", "property-testing"],
    "product-reviewer": ["product-reviewer", "architect"],
    "patch-critic": ["patch-critic", "code-reviewer"],
    "planning-agent": ["planning-agent", "architect"],
    "session-memory-updater": ["session-memory-updater"],
}


def _load_categories(role):
    text = (AGENTS_DIR / f"{role}.md").read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(match.group(1)).get("instinct_categories")


class AgentInstinctCategoriesSnapshot(unittest.TestCase):
    def test_each_agent_declares_expected_categories(self):
        for role, expected in EXPECTED.items():
            with self.subTest(role=role):
                self.assertEqual(_load_categories(role), expected)


if __name__ == "__main__":
    unittest.main()

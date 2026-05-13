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
    "architect-context-recon": ["architect", "software-engineer"],
    "code-reviewer": [
        "code-reviewer", "software-engineer",
        "frontend-engineer", "database-engineer"],
    "security-engineer": ["security-engineer"],
    "qa-engineer": ["qa-engineer", "software-engineer",
                    "property-testing", "playwright", "web-e2e"],
    "product-reviewer": ["product-reviewer", "architect"],
    "patch-critic": ["patch-critic", "patch-critic-correctness",
                     "patch-critic-regression", "patch-critic-scope",
                     "code-reviewer"],
    "planning-agent": ["planning-agent", "architect"],
    "session-memory-updater": ["session-memory-updater"],
    "sandbox-verify-engineer": ["sandbox-verify-engineer", "qa-engineer"],
    "fix-engineer": ["fix-engineer", "software-engineer"],
    "pbt-engineer": ["pbt-engineer", "qa-engineer",
                     "software-engineer", "property-testing"],
    "spec-blind-validator": ["qa-engineer", "spec-blind-validator"],
    "vlm-critic": ["qa-engineer", "vlm-critic"],
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


def _agent_files():
    """Top-level *.md files in agents/, excluding archive/ and dynamic/."""
    return sorted(
        p.stem for p in AGENTS_DIR.glob("*.md") if p.is_file()
    )


class AgentInstinctCategoriesBidirectional(unittest.TestCase):
    """Gap 4 — bidirectional lockstep: drift in either direction fails CI.

    The single-direction snapshot test above pins the categories for the
    8-ish agents listed in EXPECTED but lets new agents land without a
    pinned entry. This pair of checks closes the loop:

    - Every agent in `agents/*.md` MUST have an entry in EXPECTED (new
      agent without a pinned snapshot fails CI).
    - Every entry in EXPECTED MUST correspond to a real agent file (a
      stale EXPECTED entry after an agent rename or removal fails CI).
    """

    def test_every_agent_file_has_expected_entry(self):
        agent_names = set(_agent_files())
        expected_names = set(EXPECTED.keys())
        missing_from_expected = sorted(agent_names - expected_names)
        self.assertFalse(
            missing_from_expected,
            msg=(
                f"agents/*.md without an EXPECTED entry: "
                f"{missing_from_expected}. Add their instinct_categories "
                f"snapshot to EXPECTED in this file to lock them down."
            ),
        )

    def test_every_expected_entry_has_agent_file(self):
        agent_names = set(_agent_files())
        expected_names = set(EXPECTED.keys())
        stale_in_expected = sorted(expected_names - agent_names)
        self.assertFalse(
            stale_in_expected,
            msg=(
                f"EXPECTED entries without an agents/*.md file: "
                f"{stale_in_expected}. Remove the stale entry."
            ),
        )


if __name__ == "__main__":
    unittest.main()

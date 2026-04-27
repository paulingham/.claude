"""Roles Enforcement test for Wave 4-M Slice 5.

Asserts that every agent/*.md file declares `instinct_categories:` as a
YAML list (regression for the "lists must round-trip as Python lists, not
strings" pattern documented in scratchpad — see slice-2 build notes), and
that the dedicated loader returns a list for every shipped role and None
for unknown roles.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"
sys.path.insert(0, str(REPO_ROOT / "hooks" / "_lib"))

from agent_instinct_categories_loader import load_agent_instinct_categories


def _agent_files():
    return sorted(p for p in AGENTS_DIR.glob("*.md") if p.is_file())


def _frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return yaml.safe_load(match.group(1)) if match else {}


def _load(role):
    with patch.dict("os.environ", {"CLAUDE_AGENTS_DIR": str(AGENTS_DIR)}):
        return load_agent_instinct_categories(role)


class EveryAgentDeclaresInstinctCategories(unittest.TestCase):
    def test_field_present_on_every_agent(self):
        for path in _agent_files():
            with self.subTest(agent=path.name):
                self.assertIn("instinct_categories", _frontmatter(path))

    def test_field_is_yaml_list_not_string(self):
        for path in _agent_files():
            with self.subTest(agent=path.name):
                value = _frontmatter(path)["instinct_categories"]
                self.assertIsInstance(value, list,
                                      f"{path.name}: must be list, got "
                                      f"{type(value).__name__}")

    def test_field_is_non_empty_list(self):
        for path in _agent_files():
            with self.subTest(agent=path.name):
                self.assertGreater(
                    len(_frontmatter(path)["instinct_categories"]), 0,
                    f"{path.name}: instinct_categories must not be empty")

    def test_each_category_is_string(self):
        for path in _agent_files():
            with self.subTest(agent=path.name):
                cats = _frontmatter(path)["instinct_categories"]
                for cat in cats:
                    self.assertIsInstance(cat, str,
                                          f"{path.name}: '{cat!r}' is not str")


class LoaderReturnsListForEveryShippedRole(unittest.TestCase):
    def test_loader_returns_list_for_every_role(self):
        for path in _agent_files():
            role = path.stem
            with self.subTest(role=role):
                result = _load(role)
                self.assertIsInstance(result, list,
                                      f"{role}: loader returned "
                                      f"{type(result).__name__}, want list")
                self.assertGreater(len(result), 0,
                                   f"{role}: loader returned empty list")


class LoaderReturnsNoneForUnknownRole(unittest.TestCase):
    def test_unknown_role_returns_none(self):
        self.assertIsNone(_load("zzz-does-not-exist-role-zzz"))


if __name__ == "__main__":
    unittest.main()

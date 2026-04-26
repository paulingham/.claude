"""Shared validator for `subagent_type` strings (kebab-case, no traversal)."""
import unittest

from agent_path_validator import is_valid_subagent_type


class PathValidatorRejectsTraversal(unittest.TestCase):
    def test_rejects_traversal_input(self):
        self.assertFalse(is_valid_subagent_type("../../etc/passwd"))

    def test_rejects_empty_string(self):
        self.assertFalse(is_valid_subagent_type(""))

    def test_rejects_none(self):
        self.assertFalse(is_valid_subagent_type(None))

    def test_accepts_valid_kebab_case(self):
        self.assertTrue(is_valid_subagent_type("software-engineer"))

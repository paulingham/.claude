"""Helpers for instinct_loader: parse, validate, normalize, log."""
import unittest

from instinct_loader_helpers import extract_summary, validate


class ExtractSummary(unittest.TestCase):
    def test_skips_blank_lines_within_pattern_section(self):
        body = "## Pattern\n   \n\t\n\n## Why\nReason.\n"
        self.assertEqual(extract_summary(body), "")


class ValidateRequiresAllFields(unittest.TestCase):
    def test_returns_malformed_yaml_when_fm_is_none(self):
        self.assertEqual(validate(None, "## Pattern\nx\n"), "malformed-yaml")

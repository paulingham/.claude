"""Tests for the YAML-frontmatter splitter helper."""
import unittest

from scratchpad_frontmatter import extract_category, split_frontmatter


class SplitFrontmatterReturnsTupleWhenWellFormed(unittest.TestCase):
    def test_returns_frontmatter_and_body(self):
        result = split_frontmatter("---\ncategory: warning\n---\nbody\n")
        assert result is not None
        front, body = result
        self.assertIn("category: warning", front)
        self.assertEqual(body, "body\n")


class SplitFrontmatterReturnsNoneOnMalformed(unittest.TestCase):
    def test_no_opening_delim_returns_none(self):
        self.assertIsNone(split_frontmatter("plain body\n"))

    def test_no_closing_delim_returns_none(self):
        self.assertIsNone(split_frontmatter("---\ncategory: x\nno end\n"))


class ExtractCategoryHandlesWhitespaceAndCase(unittest.TestCase):
    def test_uppercase_category_lowercased(self):
        self.assertEqual(extract_category("category:   FRAGILITY"), "fragility")

    def test_missing_category_returns_none(self):
        self.assertIsNone(extract_category("name: foo"))


if __name__ == "__main__":
    unittest.main()

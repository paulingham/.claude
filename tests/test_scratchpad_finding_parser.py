"""Tests for the scratchpad finding parser helper.

These tests exercise the parser directly. Higher-level behavior is also
covered transitively by tests/test_scratchpad_diff.py.
"""
import tempfile
import unittest
from pathlib import Path

from scratchpad_finding_parser import content_hash, parse_finding


class ParseFindingExtractsCategoryAndBody(unittest.TestCase):
    def test_well_formed_finding_parses(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "ok.md"
            f.write_text("---\ncategory: warning\n---\nbody text\n")
            finding = parse_finding(f)
        assert finding is not None
        self.assertEqual(finding["filename"], "ok.md")
        self.assertEqual(finding["category"], "warning")
        self.assertIn("body text", finding["body"])


class ParseFindingReturnsNoneWhenInvalid(unittest.TestCase):
    def _parse(self, text: str):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "x.md"
            f.write_text(text)
            return parse_finding(f)

    def test_no_frontmatter_returns_none(self):
        self.assertIsNone(self._parse("just a body\n"))

    def test_no_category_returns_none(self):
        self.assertIsNone(self._parse("---\nname: foo\n---\nbody\n"))


class ContentHashIsDeterministic(unittest.TestCase):
    def test_same_input_yields_same_hash(self):
        self.assertEqual(content_hash(b"x"), content_hash(b"x"))

    def test_hash_is_16_hex_chars(self):
        h = content_hash(b"abc")
        self.assertEqual(len(h), 16)
        int(h, 16)


if __name__ == "__main__":
    unittest.main()

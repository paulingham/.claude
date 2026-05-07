"""AC7 — Empty-body skip rule.

When a sub-file's body (after stripping leading '# ' header lines, '_…_'
italic-description lines, and blank lines) is < 50 chars, the orchestrator's
injection helper omits that sub-file from the rendered block. When >= 50,
include it.

The helper exposes:
    body_chars(text) -> int       # post-strip byte count of the body
    should_inject_subfile(text) -> bool  # body_chars(text) >= 50
"""
import unittest

from session_memory_role_resolver import body_chars, should_inject_subfile


class BodyCharsStripsHeaderItalicAndBlankLines(unittest.TestCase):
    def test_empty_template_only_yields_zero_body_chars(self):
        text = "# Build & Test\n_What builds, what tests._\n"
        self.assertEqual(body_chars(text), 0)

    def test_blank_lines_excluded_from_count(self):
        text = "# Title\n_desc_\n\n\n"
        self.assertEqual(body_chars(text), 0)

    def test_body_chars_counts_real_content(self):
        text = "# Title\n_desc_\nhello world\n"  # 'hello world' = 11 chars
        self.assertEqual(body_chars(text), len("hello world"))


class FortyNineCharsSkippedFiftyCharsIncluded(unittest.TestCase):
    def test_49_chars_skipped(self):
        body = "x" * 49
        text = f"# Title\n_desc_\n{body}\n"
        self.assertEqual(body_chars(text), 49)
        self.assertFalse(should_inject_subfile(text))

    def test_50_chars_included(self):
        body = "x" * 50
        text = f"# Title\n_desc_\n{body}\n"
        self.assertEqual(body_chars(text), 50)
        self.assertTrue(should_inject_subfile(text))


if __name__ == "__main__":
    unittest.main()

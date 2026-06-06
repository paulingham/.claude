"""Tests for swe_pruner syntax guard — AC3 detailed, AC5 invariant.

Primary: fenced-code and YAML frontmatter fences.
Secondary: embedded source-code patterns (import/def/class/shebang/export).
"""
import sys
import unittest
from pathlib import Path

_HOOKS_LIB = str(Path(__file__).resolve().parents[1] / "hooks" / "_lib")
if _HOOKS_LIB not in sys.path:
    sys.path.insert(0, _HOOKS_LIB)


class TestSyntaxScaffoldPrimary(unittest.TestCase):
    """Primary scaffold patterns: markdown fences."""

    def test_triple_backtick_open_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("```"))

    def test_triple_backtick_with_language_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("```python"))
        self.assertTrue(is_syntax_scaffold("```bash"))
        self.assertTrue(is_syntax_scaffold("```json"))
        self.assertTrue(is_syntax_scaffold("```yaml"))

    def test_yaml_frontmatter_triple_dash_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("---"))

    def test_triple_backtick_with_leading_spaces_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("   ```python"))


class TestSyntaxScaffoldSecondary(unittest.TestCase):
    """Secondary scaffold patterns: source-code identifiers."""

    def test_python_import_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("import os"))
        self.assertTrue(is_syntax_scaffold("import sys"))

    def test_from_import_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("from pathlib import Path"))

    def test_class_definition_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("class Foo:"))
        self.assertTrue(is_syntax_scaffold("class Foo(Bar):"))

    def test_def_definition_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("def my_func():"))
        self.assertTrue(is_syntax_scaffold("def __init__(self):"))

    def test_shebang_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("#!/usr/bin/env bash"))
        self.assertTrue(is_syntax_scaffold("#!/usr/bin/python3"))

    def test_export_function_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("export function myFunc()"))
        self.assertTrue(is_syntax_scaffold("export default class"))


class TestSyntaxScaffoldFalseNegatives(unittest.TestCase):
    """Lines that should NOT be classified as scaffold."""

    def test_plain_prose_is_not_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertFalse(is_syntax_scaffold("This is a plain sentence."))
        self.assertFalse(is_syntax_scaffold("The service failed to start."))

    def test_markdown_header_is_not_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertFalse(is_syntax_scaffold("## Section Header"))
        self.assertFalse(is_syntax_scaffold("# Top-Level Header"))

    def test_empty_line_is_not_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertFalse(is_syntax_scaffold(""))

    def test_whitespace_only_is_not_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertFalse(is_syntax_scaffold("   "))
        self.assertFalse(is_syntax_scaffold("\t"))

    def test_bullet_list_is_not_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertFalse(is_syntax_scaffold("- item one"))
        self.assertFalse(is_syntax_scaffold("* bullet point"))

    def test_prose_mentioning_import_is_not_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        # "The import of the package..." — should not trigger
        # Only exact leading pattern matters
        self.assertFalse(is_syntax_scaffold("We need to re-import the module"))


class TestProposedDropsNeverIncludesScaffold(unittest.TestCase):
    """INVARIANT 2: propose_drops NEVER includes syntax scaffold lines."""

    def test_block_with_only_scaffold_has_zero_drops(self):
        from swe_pruner import segment_content_blocks, propose_drops
        # A block composed entirely of fence markers and imports
        scaffold_content = "\n".join([
            "```python",
            "import os",
            "import sys",
            "class MyClass:",
            "    def method(self):",
            "        pass",
            "```",
        ])
        prompt = f"## Scratchpad\n{scaffold_content}\n"
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["database", "migration", "unrelated"])
        ranges = propose_drops(blocks[0], keywords)
        total_dropped = sum(end - start for start, end in ranges)
        # No scaffold lines should be dropped
        # The blank line and "pass" are not scaffold, but "```", "import", "class", "def" are
        for start, end in ranges:
            for i in range(start, end):
                line = blocks[0].lines[i]
                from swe_pruner import is_syntax_scaffold
                self.assertFalse(
                    is_syntax_scaffold(line),
                    f"Scaffold line proposed for drop at index {i}: {line!r}"
                )

    def test_mixed_block_scaffold_lines_never_dropped(self):
        from swe_pruner import segment_content_blocks, propose_drops, is_syntax_scaffold
        # Mix of scaffold and irrelevant prose
        mixed_content = "\n".join([
            "```python",
            "irrelevant content about weather",
            "the fox jumped over the dog",
            "import os",
            "more irrelevant weather discussion",
            "```",
        ])
        prompt = f"## Protocol\n{mixed_content}\n"
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["authentication", "database"])
        ranges = propose_drops(blocks[0], keywords)
        for start, end in ranges:
            for i in range(start, end):
                line = blocks[0].lines[i]
                self.assertFalse(
                    is_syntax_scaffold(line),
                    f"Scaffold line at index {i} proposed for drop: {line!r}"
                )


if __name__ == "__main__":
    unittest.main()

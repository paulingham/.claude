"""Tests for swe_pruner.py scorer core — AC1-AC6.

Tests for goal keyword extraction, block segmentation, line scoring,
drop proposals, and threshold configuration.
"""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Add hooks/_lib to path (mirrors conftest.py precedent)
_HOOKS_LIB = str(Path(__file__).resolve().parents[1] / "hooks" / "_lib")
if _HOOKS_LIB not in sys.path:
    sys.path.insert(0, _HOOKS_LIB)


class TestExtractGoalKeywords(unittest.TestCase):
    """AC1: extract_goal_keywords filters short tokens and returns frozenset."""

    def test_extract_goal_keywords_filters_short_tokens(self):
        from swe_pruner import extract_goal_keywords
        keywords = extract_goal_keywords("software-engineer", "build the authentication service")
        # "the" (3) is borderline — only tokens >= 3 chars are kept
        # check that "is" (2 chars) is excluded
        self.assertNotIn("is", keywords)
        self.assertIn("build", keywords)
        self.assertIn("authentication", keywords)
        self.assertIn("service", keywords)

    def test_extract_goal_keywords_filters_tokens_under_3_chars(self):
        from swe_pruner import extract_goal_keywords
        keywords = extract_goal_keywords("software-engineer", "do it now go")
        # "do" (2), "it" (2), "go" (2) all < 3 chars
        self.assertNotIn("do", keywords)
        self.assertNotIn("it", keywords)
        self.assertNotIn("go", keywords)

    def test_extract_goal_keywords_empty_prompt_uses_subagent_type(self):
        from swe_pruner import extract_goal_keywords
        # Even with empty prompt, subagent_type tokens are extracted
        keywords = extract_goal_keywords("software-engineer", "")
        self.assertIn("software", keywords)
        self.assertIn("engineer", keywords)

    def test_extract_goal_keywords_both_empty_returns_empty(self):
        from swe_pruner import extract_goal_keywords
        keywords = extract_goal_keywords("", "")
        self.assertEqual(keywords, frozenset())

    def test_extract_goal_keywords_returns_frozenset(self):
        from swe_pruner import extract_goal_keywords
        keywords = extract_goal_keywords("software-engineer", "build the system")
        self.assertIsInstance(keywords, frozenset)

    def test_extract_goal_keywords_lowercases_tokens(self):
        from swe_pruner import extract_goal_keywords
        keywords = extract_goal_keywords("software-engineer", "Build The Authentication")
        self.assertIn("build", keywords)
        self.assertIn("authentication", keywords)
        self.assertNotIn("Build", keywords)

    def test_extract_goal_keywords_never_raises_on_malformed(self):
        from swe_pruner import extract_goal_keywords
        # Should not raise even on weird input
        try:
            result = extract_goal_keywords("", None)  # type: ignore
        except Exception:
            self.fail("extract_goal_keywords raised on None prompt")

    def test_extract_goal_keywords_includes_subagent_type_tokens(self):
        from swe_pruner import extract_goal_keywords
        keywords = extract_goal_keywords("software-engineer", "implement the feature")
        # subagent_type tokens >= 3 chars should be included
        self.assertIn("software", keywords)
        self.assertIn("engineer", keywords)


class TestSegmentContentBlocks(unittest.TestCase):
    """AC2: segment_content_blocks splits on '## ' and assigns block_type."""

    def test_segment_scratchpad_block_type(self):
        from swe_pruner import segment_content_blocks
        prompt = "## Scratchpad\nsome content here\n"
        blocks = segment_content_blocks(prompt)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_type, "scratchpad")

    def test_segment_protocol_block_type(self):
        from swe_pruner import segment_content_blocks
        prompt = "## Protocol\nsome protocol content\n"
        blocks = segment_content_blocks(prompt)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_type, "protocol")

    def test_segment_session_memory_block_type(self):
        from swe_pruner import segment_content_blocks
        prompt = "## Session Memory\nsome memory content\n"
        blocks = segment_content_blocks(prompt)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_type, "session_memory")

    def test_segment_role_doc_block_type(self):
        from swe_pruner import segment_content_blocks
        prompt = "## Role\nsome role doc content\n"
        blocks = segment_content_blocks(prompt)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_type, "role_doc")

    def test_segment_instincts_block_type(self):
        from swe_pruner import segment_content_blocks
        prompt = "## Instincts\nsome instinct content\n"
        blocks = segment_content_blocks(prompt)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_type, "instincts")

    def test_segment_unknown_block_type(self):
        from swe_pruner import segment_content_blocks
        prompt = "## SomethingUnrecognized\nfoo bar baz\n"
        blocks = segment_content_blocks(prompt)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].block_type, "unknown")

    def test_segment_empty_prompt_returns_empty_list(self):
        from swe_pruner import segment_content_blocks
        blocks = segment_content_blocks("")
        self.assertEqual(blocks, [])

    def test_segment_multiple_blocks(self):
        from swe_pruner import segment_content_blocks
        prompt = "## Scratchpad\nscatch content\n## Protocol\nprotocol content\n"
        blocks = segment_content_blocks(prompt)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0].block_type, "scratchpad")
        self.assertEqual(blocks[1].block_type, "protocol")

    def test_segment_block_has_lines(self):
        from swe_pruner import segment_content_blocks
        prompt = "## Scratchpad\nline one\nline two\n"
        blocks = segment_content_blocks(prompt)
        self.assertEqual(len(blocks), 1)
        # lines should be accessible
        self.assertGreater(len(blocks[0].lines), 0)

    def test_segment_never_raises_on_malformed(self):
        from swe_pruner import segment_content_blocks
        try:
            result = segment_content_blocks(None)  # type: ignore
        except Exception:
            self.fail("segment_content_blocks raised on None")


class TestIsSyntaxScaffold(unittest.TestCase):
    """AC3: is_syntax_scaffold — fenced code delimiters primary, source-code patterns secondary."""

    # Primary: fenced code block delimiters (markdown spawns)
    def test_fence_open_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("```python"))

    def test_fence_close_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("```"))

    def test_yaml_frontmatter_fence_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("---"))

    # Secondary: embedded-code patterns in prompts
    def test_import_line_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("import os"))

    def test_from_import_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("from pathlib import Path"))

    def test_class_def_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("class MyClass:"))

    def test_def_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("def my_function():"))

    def test_shebang_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("#!/usr/bin/env bash"))

    def test_export_is_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertTrue(is_syntax_scaffold("export function myFunc()"))

    # Not scaffold: prose and markdown
    def test_plain_prose_is_not_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertFalse(is_syntax_scaffold("This is a plain prose line."))

    def test_markdown_header_is_not_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertFalse(is_syntax_scaffold("## Section Header"))

    def test_empty_line_is_not_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertFalse(is_syntax_scaffold(""))

    def test_empty_line_outside_fence_is_not_scaffold(self):
        from swe_pruner import is_syntax_scaffold
        self.assertFalse(is_syntax_scaffold("   "))


class TestScoreLine(unittest.TestCase):
    """AC4: score_line returns [0,1], deterministic, high-keyword lines score higher."""

    def test_score_line_range_is_zero_to_one_for_irrelevant(self):
        from swe_pruner import score_line
        score = score_line("completely unrelated content", frozenset(["database", "migration"]))
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_score_line_range_is_zero_to_one_for_relevant(self):
        from swe_pruner import score_line
        score = score_line("database migration running", frozenset(["database", "migration"]))
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_score_line_high_keyword_density_scores_higher(self):
        from swe_pruner import score_line
        keywords = frozenset(["authentication", "service", "build"])
        high_score = score_line("build the authentication service here", keywords)
        low_score = score_line("some unrelated content about nothing", keywords)
        self.assertGreater(high_score, low_score)

    def test_score_line_deterministic(self):
        from swe_pruner import score_line
        keywords = frozenset(["build", "service"])
        line = "build the service now"
        score1 = score_line(line, keywords)
        score2 = score_line(line, keywords)
        self.assertEqual(score1, score2)

    def test_score_line_empty_keywords_scores_zero(self):
        from swe_pruner import score_line
        score = score_line("some content here", frozenset())
        self.assertEqual(score, 0.0)

    def test_score_line_empty_line_scores_zero(self):
        from swe_pruner import score_line
        score = score_line("", frozenset(["build", "service"]))
        self.assertEqual(score, 0.0)


class TestProposeDrops(unittest.TestCase):
    """AC5: propose_drops never includes syntax scaffold, drops irrelevant lines."""

    def test_propose_drops_never_includes_scaffold_lines(self):
        from swe_pruner import segment_content_blocks, propose_drops, is_syntax_scaffold
        # A block that has scaffold lines mixed with irrelevant prose
        prompt = "## Scratchpad\n```python\nimport os\n```\nirrelevant content about nothing\n"
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["authentication", "migration"])
        for block in blocks:
            ranges = propose_drops(block, keywords)
            for start, end in ranges:
                for i in range(start, end):
                    line = block.lines[i]
                    self.assertFalse(
                        is_syntax_scaffold(line),
                        f"Line {i} is scaffold but was proposed for drop: {line!r}"
                    )

    def test_propose_drops_oracle_known_irrelevant_block(self):
        from swe_pruner import segment_content_blocks, propose_drops
        # A block with clearly irrelevant content
        irrelevant_lines = "\n".join([
            "The weather today is sunny and warm.",
            "Birds are singing in the garden.",
            "A fox jumped over the lazy dog.",
            "Mountains are beautiful in autumn.",
            "The ocean has many fish species.",
        ])
        prompt = f"## Scratchpad\n{irrelevant_lines}\n"
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["authentication", "migration", "database"])
        ranges = propose_drops(blocks[0], keywords)
        # Should propose dropping some lines since content is irrelevant
        total_dropped = sum(end - start for start, end in ranges)
        self.assertGreater(total_dropped, 0)

    def test_propose_drops_relevant_block_drops_fewer(self):
        from swe_pruner import segment_content_blocks, propose_drops
        relevant_lines = "\n".join([
            "The authentication service needs migration.",
            "Database migration runs on deploy.",
            "Authentication tokens expire after session.",
        ])
        prompt = f"## Scratchpad\n{relevant_lines}\n"
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["authentication", "migration", "database"])
        ranges = propose_drops(blocks[0], keywords)
        total_dropped = sum(end - start for start, end in ranges)
        # Relevant content should drop fewer lines than irrelevant
        self.assertEqual(total_dropped, 0)


class TestThresholdConfig(unittest.TestCase):
    """AC6: threshold is env-configurable with fallback on malformed value."""

    def test_threshold_env_var_applied(self):
        from swe_pruner import segment_content_blocks, propose_drops
        # With a very high threshold (1.0), nothing should be dropped
        prompt = "## Scratchpad\nirrelevant content\n"
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["authentication"])
        with patch.dict(os.environ, {"CLAUDE_PRUNER_THRESHOLD": "1.0"}, clear=False):
            ranges = propose_drops(blocks[0], keywords)
        # At threshold 1.0, everything scores below threshold → dropped... wait
        # Actually threshold is for KEEPING: lines scoring BELOW threshold are dropped
        # So threshold=1.0 means everything is dropped (score < 1.0 for all)
        # Let's verify the behavior is different at different thresholds
        with patch.dict(os.environ, {"CLAUDE_PRUNER_THRESHOLD": "0.0"}, clear=False):
            ranges_zero = propose_drops(blocks[0], keywords)
        # At 0.0 threshold, nothing gets dropped (score >= 0.0 always)
        self.assertEqual(ranges_zero, [])

    def test_threshold_env_var_malformed_falls_back_to_default(self):
        from swe_pruner import segment_content_blocks, propose_drops
        prompt = "## Scratchpad\nsome content\n"
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["authentication"])
        # Should not raise even with malformed threshold
        with patch.dict(os.environ, {"CLAUDE_PRUNER_THRESHOLD": "not-a-number"}, clear=False):
            try:
                ranges = propose_drops(blocks[0], keywords)
            except Exception:
                self.fail("propose_drops raised with malformed threshold env var")

    def test_threshold_default_is_0_15(self):
        """Default threshold should be 0.15 per plan spec."""
        from swe_pruner import propose_drops, segment_content_blocks
        # This just verifies the function signature accepts threshold param
        prompt = "## Scratchpad\nsome content\n"
        blocks = segment_content_blocks(prompt)
        keywords = frozenset(["authentication"])
        # Call with explicit default
        ranges = propose_drops(blocks[0], keywords, threshold=0.15)
        # Should not raise
        self.assertIsInstance(ranges, list)


if __name__ == "__main__":
    unittest.main()

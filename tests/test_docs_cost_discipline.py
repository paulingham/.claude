"""Slice B' AC5 — CLAUDE.md grows a Cost Discipline section.

Inserted between § Advisor-Mode Reviews and § Per-Agent Tool Allowlists.
≤ 30 lines body, names the May 8 subagent-summary cache fix and its
cache-stability precondition, cross-links the cost-report skill.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def _cost_discipline_body():
    """Return the body lines between `### Cost Discipline` and the next `### `.

    Returns the empty list when the heading is absent — that case is
    asserted explicitly by CostDisciplineSectionExists.
    """
    content = CLAUDE_MD.read_text()
    match = re.search(
        r"^###\s+Cost Discipline\s*$(.+?)(?=^###\s+|\Z)",
        content, re.DOTALL | re.MULTILINE)
    if not match:
        return []
    return match.group(1).splitlines()


class CostDisciplineSectionExists(unittest.TestCase):
    """AC5: the `### Cost Discipline` heading is present in CLAUDE.md."""

    def test_claude_md_has_cost_discipline_heading(self):
        content = CLAUDE_MD.read_text()
        self.assertIn(
            "### Cost Discipline", content,
            "CLAUDE.md must contain a `### Cost Discipline` subsection "
            "(AC5 deliverable).")


class CostDisciplineSectionBounded(unittest.TestCase):
    """AC5: the section body is ≤ 30 lines (plan exit criterion)."""

    def test_cost_discipline_section_at_most_30_lines(self):
        body = _cost_discipline_body()
        self.assertTrue(
            body,
            "Cost Discipline section body could not be located — heading "
            "must be present before line-count can be asserted.")
        # Strip the leading blank line that always follows a heading; count
        # the actual content lines that fall inside the section.
        non_empty_or_padding = body  # All lines, including blanks, count.
        self.assertLessEqual(
            len(non_empty_or_padding), 30,
            f"Cost Discipline section body must be ≤ 30 lines (plan exit "
            f"criterion). Found {len(non_empty_or_padding)} lines.")


class CacheStableClaim(unittest.TestCase):
    """AC5: the section names the cache-stability precondition explicitly."""

    def test_cost_discipline_names_cache_stable_preambles(self):
        body_text = "\n".join(_cost_discipline_body())
        self.assertTrue(
            body_text,
            "Cost Discipline section body must be present before content "
            "can be asserted.")
        # Either spelling is acceptable; the load-bearing concept is that
        # the ~3x reduction is conditional on cache stability.
        cache_tokens = ("cache-stable", "cache_stable")
        present = [t for t in cache_tokens if t in body_text]
        self.assertTrue(
            present,
            f"Cost Discipline section must name one of {cache_tokens!r} — "
            f"the cache-stability precondition is the load-bearing claim.")
        # The fix that motivates the section — names the actual change.
        self.assertIn(
            "subagent-summary", body_text,
            "Cost Discipline section must name the `subagent-summary` cache "
            "fix that motivates the section.")


if __name__ == "__main__":
    unittest.main()

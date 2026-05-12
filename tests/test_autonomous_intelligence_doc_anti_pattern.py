"""C8 S6: anti-pattern documentation snapshots.

Three snapshot tests pinning the doc updates that ship in C8:
  AC6.1 — § Scratchpad → Instinct Promotion mentions anti-pattern +
          the recurrence rule (3+ pipelines, or equivalent wording).
  AC6.2 — § Instinct Injection documents the +0.1 floor boost,
          located within 200 chars of "anti-pattern".
  AC6.3 — skills/learn/SKILL.md Step 5 lists all six categories
          including anti-pattern.

These tests guard against silent doc drift — if a future edit removes
the anti-pattern mention or the +0.1 boost discussion, CI fails.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "protocols" / "autonomous-intelligence.md"
SKILL_PATH = REPO_ROOT / "skills" / "learn" / "SKILL.md"


def _section(text, header_pattern, until_pattern):
    """Slice `text` between the next match of header_pattern and the next
    line beginning with until_pattern (search begins on the line AFTER
    the header). Returns the section body (incl. header line)."""
    m = re.search(header_pattern, text, re.MULTILINE)
    if not m:
        return None
    # Skip past the header line so until_pattern doesn't re-match it.
    body_start = text.find("\n", m.end())
    if body_start == -1:
        return text[m.start():]
    body = text[body_start:]
    end = re.search(until_pattern, body, re.MULTILINE)
    if end is None:
        return text[m.start():]
    return text[m.start():body_start + end.start()]


class DocReferencesAntiPatternCategory(unittest.TestCase):
    """§ Scratchpad → Instinct Promotion mentions the anti-pattern
    recurrence rule. The section is bullet-formatted (not tabular) —
    we assert substring presence, not table-row shape.
    """

    def test_scratchpad_promotion_section_mentions_anti_pattern_recurrence_rule(
            self):
        text = DOC_PATH.read_text()
        section = _section(
            text,
            r"^### Scratchpad → Instinct Promotion$",
            r"^### ")
        self.assertIsNotNone(
            section,
            "Could not locate § Scratchpad → Instinct Promotion in "
            "protocols/autonomous-intelligence.md")
        lower = section.lower()
        self.assertIn("anti-pattern", lower,
                      "section must mention the anti-pattern category")
        # Recurrence rule wording: "3+ pipelines" OR "three pipelines"
        # OR "rounds >= 2" — any one is acceptable.
        self.assertTrue(
            "3+ pipelines" in lower
            or "three pipelines" in lower
            or "rounds >= 2" in lower,
            "section must document the recurrence threshold")


class DocReferencesPlus01Boost(unittest.TestCase):
    """§ Instinct Injection (or a sibling subsection) documents the
    +0.1 floor boost; the literal "+0.1" must sit within 200 chars
    of the word "anti-pattern" so the two concepts are visibly linked.
    """

    def test_instinct_injection_section_documents_floor_boost(self):
        text = DOC_PATH.read_text()
        # Slice from § Instinct Injection through to the next top-level
        # ## section so the search covers all subsections under it.
        section = _section(
            text,
            r"^### Instinct Injection",
            r"^## ")
        self.assertIsNotNone(
            section,
            "Could not locate § Instinct Injection in "
            "protocols/autonomous-intelligence.md")
        lower = section.lower()
        self.assertIn("+0.1", lower,
                      "Injection section must document the +0.1 boost")
        self.assertIn("anti-pattern", lower,
                      "Injection section must mention anti-pattern")
        # Within-200-char proximity check: find every +0.1 occurrence
        # and confirm at least one is within 200 chars of "anti-pattern".
        positions_boost = [
            m.start() for m in re.finditer(re.escape("+0.1"), lower)]
        positions_ap = [
            m.start() for m in re.finditer(re.escape("anti-pattern"), lower)]
        within_window = any(
            abs(b - a) <= 200
            for b in positions_boost for a in positions_ap)
        self.assertTrue(
            within_window,
            "+0.1 must appear within 200 chars of an anti-pattern mention")


class LearnSkillDocAddsAntiPatternToCategoryEnum(unittest.TestCase):
    """`skills/learn/SKILL.md` Step 5 lists all six categories,
    including anti-pattern."""

    def test_skill_md_step5_lists_anti_pattern_category(self):
        text = SKILL_PATH.read_text()
        section = _section(
            text,
            r"^### 5\. Create or Update Instincts",
            r"^### 6\.")
        self.assertIsNotNone(
            section,
            "Could not locate § 5 in skills/learn/SKILL.md")
        for cat in ("discovery", "warning", "pattern", "fragility",
                    "decision", "anti-pattern"):
            with self.subTest(category=cat):
                self.assertIn(
                    cat, section,
                    f"Step 5 category enum must include '{cat}'")


if __name__ == "__main__":
    unittest.main()

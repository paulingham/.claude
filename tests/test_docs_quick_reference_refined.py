"""Slice B' AC6a/b/c/d — CLAUDE.md Quick Reference hedge refinements.

Four Quick Reference subsections refresh their hedge wording for v2.1.140:

- AC6a § Thinking Defaults — clarify per-spawn `tool_input.thinking.effort`
  is not yet exposed; advisory framing retained (AC1 dropped).
- AC6b § Advisor-Mode Reviews — clarify `advisor:` field not yet exposed.
- AC6c § Per-Agent Tool Allowlists — clarify `allowed_tools:` field not yet
  exposed.
- AC6d § Instinct Injection — clarify `modified_tool_input` not yet exposed
  (symmetry edit flagged by archaeology recon §6).

Every section retains the "advisory" claim — none claim enforcement.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


def _section_body(heading):
    """Return the body text between `### {heading}` and the next `### `.

    Empty string when the heading is absent — caller handles the
    missing-section case explicitly.
    """
    content = CLAUDE_MD.read_text()
    pattern = (
        r"^###\s+" + re.escape(heading)
        + r"\s*$(.+?)(?=^###\s+|\Z)")
    match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
    return match.group(1) if match else ""


class ThinkingHedgeRefined(unittest.TestCase):
    """AC6a: § Thinking Defaults — advisory framing retained, schema gap
    named precisely. AC1 was dropped from this pipeline; the section must
    NOT claim enforcement."""

    def test_thinking_defaults_section_clarifies_schema_gap(self):
        body = _section_body("Thinking Defaults (Opus 4.7)")
        self.assertTrue(
            body,
            "CLAUDE.md must contain a `### Thinking Defaults (Opus 4.7)` "
            "subsection.")
        # Advisory framing retained — either token is acceptable.
        advisory_tokens = ("log-only", "advisory")
        present = [t for t in advisory_tokens if t in body]
        self.assertTrue(
            present,
            f"§ Thinking Defaults must retain advisory framing — one of "
            f"{advisory_tokens!r} must survive. AC1 (hook enforcement) was "
            f"dropped from this pipeline; the doc must reflect that.")
        # The per-spawn field path that v2.1.140 still does NOT expose.
        self.assertIn(
            "tool_input.thinking.effort", body,
            "§ Thinking Defaults must name the per-spawn field path "
            "`tool_input.thinking.effort` so the schema gap is precise.")
        # The hedge phrasing that anchors the gap to a future release.
        self.assertIn(
            "not yet exposed", body,
            "§ Thinking Defaults must state the per-spawn field is "
            "`not yet exposed` at v2.1.140.")


class AdvisorHedgeRefined(unittest.TestCase):
    """AC6b: § Advisor-Mode Reviews — wording refresh, advisory retained."""

    def test_advisor_section_clarifies_v2_1_140_gap(self):
        body = _section_body("Advisor-Mode Reviews (Opus 4.7)")
        self.assertTrue(
            body,
            "CLAUDE.md must contain a `### Advisor-Mode Reviews (Opus 4.7)` "
            "subsection.")
        # The schema field that's still not exposed.
        self.assertIn(
            "advisor:", body,
            "§ Advisor-Mode Reviews must name the `advisor:` field as the "
            "schema surface that is not yet exposed.")
        # Advisory framing retained.
        self.assertIn(
            "advisory", body,
            "§ Advisor-Mode Reviews must retain the `advisory` claim — "
            "the `advisor:` field stays not-yet-schema-exposed at v2.1.140.")
        # Either the version pin or the explicit hedge phrasing.
        gap_tokens = ("v2.1.140", "not yet schema-exposed")
        present = [t for t in gap_tokens if t in body]
        self.assertTrue(
            present,
            f"§ Advisor-Mode Reviews must reference one of {gap_tokens!r} "
            f"to clarify the v2.1.140-specific gap.")


class AllowlistHedgeRefined(unittest.TestCase):
    """AC6c: § Per-Agent Tool Allowlists — wording refresh, advisory
    retained."""

    def test_allowlist_section_clarifies_v2_1_140_gap(self):
        body = _section_body("Per-Agent Tool Allowlists (Path B)")
        self.assertTrue(
            body,
            "CLAUDE.md must contain a `### Per-Agent Tool Allowlists "
            "(Path B)` subsection.")
        # The schema field that's still not exposed.
        self.assertIn(
            "allowed_tools:", body,
            "§ Per-Agent Tool Allowlists must name the `allowed_tools:` "
            "field as the schema surface that is not yet exposed.")
        # Advisory framing retained.
        self.assertIn(
            "advisory", body,
            "§ Per-Agent Tool Allowlists must retain the `advisory` claim "
            "— the `allowed_tools:` field stays not-yet-schema-exposed at "
            "v2.1.140.")
        # Either the version pin or the explicit hedge phrasing.
        gap_tokens = ("v2.1.140", "not yet schema-exposed")
        present = [t for t in gap_tokens if t in body]
        self.assertTrue(
            present,
            f"§ Per-Agent Tool Allowlists must reference one of "
            f"{gap_tokens!r} to clarify the v2.1.140-specific gap.")


class InstinctInjectionHedgeRefined(unittest.TestCase):
    """AC6d: § Instinct Injection — symmetry edit, advisory retained."""

    def test_instinct_injection_section_clarifies_v2_1_140_gap(self):
        body = _section_body("Instinct Injection (Path B)")
        self.assertTrue(
            body,
            "CLAUDE.md must contain a `### Instinct Injection (Path B)` "
            "subsection.")
        # The schema field that's still not exposed.
        self.assertIn(
            "modified_tool_input", body,
            "§ Instinct Injection must name the `modified_tool_input` "
            "field as the schema surface that is not yet exposed.")
        # Advisory framing retained — symmetry with AC6b/c.
        self.assertIn(
            "advisory", body,
            "§ Instinct Injection must retain the `advisory` claim — "
            "symmetry with §§ Advisor-Mode Reviews and Per-Agent Tool "
            "Allowlists at v2.1.140.")


if __name__ == "__main__":
    unittest.main()

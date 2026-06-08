"""v2.1.140 Quick Reference hedge wording — now lives in the protocol files.

CLAUDE.md was deliberately pruned to one-line pointers (commit b606d59
"prune CLAUDE.md to pointers"; #127 "trim to 171 lines per cost-management").
The detailed hedge wording these tests pin was moved out of CLAUDE.md into the
per-topic protocol files; the assertions are repointed accordingly:

- § Thinking Defaults    -> protocols/thinking-defaults.md
- § Advisor-Mode Reviews -> protocols/advisor-mode.md
- § Instinct Injection   -> protocols/autonomous-intelligence.md

The former § Per-Agent Tool Allowlists hedge test was deleted: the allowlist
gate was promoted from advisory to ENFORCING on 2026-05-14 (#146), so the
"`allowed_tools:` not yet schema-exposed" hedge it pinned no longer exists.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOLS = REPO_ROOT / "protocols"


class ThinkingHedgeRefined(unittest.TestCase):
    """§ Thinking Defaults — advisory framing retained, schema gap named
    precisely. The doc must NOT claim enforcement."""

    def test_thinking_defaults_section_clarifies_schema_gap(self):
        body = (PROTOCOLS / "thinking-defaults.md").read_text()
        # Advisory framing retained — either token is acceptable.
        advisory_tokens = ("log-only", "advisory")
        present = [t for t in advisory_tokens if t in body]
        self.assertTrue(
            present,
            f"protocols/thinking-defaults.md must retain advisory framing — "
            f"one of {advisory_tokens!r} must survive.")
        # The per-spawn field path that v2.1.140 still does NOT expose.
        self.assertIn(
            "tool_input.thinking.effort", body,
            "protocols/thinking-defaults.md must name the per-spawn field "
            "path `tool_input.thinking.effort` so the schema gap is precise.")
        self.assertIn(
            "not yet exposed", body,
            "protocols/thinking-defaults.md must state the per-spawn field is "
            "`not yet exposed`.")


class AdvisorHedgeRefined(unittest.TestCase):
    """§ Advisor-Mode Reviews — wording refresh, advisory retained."""

    def test_advisor_section_clarifies_v2_1_140_gap(self):
        body = (PROTOCOLS / "advisor-mode.md").read_text()
        self.assertIn(
            "advisor:", body,
            "protocols/advisor-mode.md must name the `advisor:` field as the "
            "schema surface that is not yet exposed.")
        self.assertIn(
            "advisory", body,
            "protocols/advisor-mode.md must retain the `advisory` claim.")
        gap_tokens = ("v2.1.140", "not yet schema-exposed")
        present = [t for t in gap_tokens if t in body]
        self.assertTrue(
            present,
            f"protocols/advisor-mode.md must reference one of {gap_tokens!r} "
            f"to clarify the v2.1.140-specific gap.")


class InstinctInjectionHedgeRefined(unittest.TestCase):
    """§ Instinct Injection — symmetry edit, advisory retained."""

    def test_instinct_injection_section_clarifies_v2_1_140_gap(self):
        body = (PROTOCOLS / "autonomous-intelligence.md").read_text()
        self.assertIn(
            "modified_tool_input", body,
            "protocols/autonomous-intelligence.md must name the "
            "`modified_tool_input` field as the schema surface not yet "
            "exposed.")
        self.assertIn(
            "advisory", body,
            "protocols/autonomous-intelligence.md must retain the `advisory` "
            "claim.")


if __name__ == "__main__":
    unittest.main()

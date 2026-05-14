"""Slice C AC-C3 + AC-C4 — protocols/cost-discipline.md rewrite assertions.

AC-C3 (six required disclosure elements in §17-22):
  (a) Drop "Upcoming" qualifier from the heading
  (b) Point at shipped hooks/cache-breakpoint-injector.sh + skills/cache-audit/SKILL.md
  (c) Document Path-B advisory/log-only status with cache-breakpoint-injector.sh:28-29 reference
  (d) Cite ProjectDiscovery's 70% case study (verbatim sentence template; READ_RATIO_TARGET = 0.60)
  (e) Enumerate BOTH upstream dependencies + the 3 follow-up tickets
  (f) State "Hook fires on tool_name == \"Agent\" PreToolUse events only" verbatim

AC-C4: §23-27 Per-Spawn Measurement Surface gains 4th bullet citing new artefacts;
       §29-32 See Also gains skills/cache-audit/SKILL.md link.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "protocols" / "cost-discipline.md"

PROJECTDISCOVERY_SENTENCE = (
    "ProjectDiscovery reports a ~70% cache read ratio with multi-anchor "
    "enforced caching across their full preamble surface. The harness "
    "targets `READ_RATIO_TARGET = 0.60` — one decimal below their measured "
    "ratio, intentionally conservative because the harness ships only one "
    "of four anchors (`rules-core-tail`) and only at advisory level until "
    "two upstream dependencies land."
)

AGENT_TOOL_ONLY_SENTENCE = (
    "Hook fires on `tool_name == \"Agent\"` PreToolUse events only. Skill "
    "invocations and other tool spawns are out of scope; the May 8 2026 "
    "subagent-summary cache fix already covers Skill-invocation cache reads "
    "via the orthogonal SubagentStop tap."
)

FOLLOWUP_TICKETS = (
    "prompt-caching-persona-marker",
    "prompt-caching-protocol-splice",
    "prompt-caching-rules-core-splice",
)


class CostDisciplineRewrite(unittest.TestCase):
    def test_cost_discipline_no_longer_says_upcoming_and_names_all_six_disclosure_elements(self):
        text = DOC.read_text()
        # (a) drop "Upcoming" qualifier — the old heading must be gone.
        self.assertNotIn(
            "Prompt-Caching Breakpoint Work (Upcoming)", text,
            "Heading `(Upcoming)` qualifier must be removed")
        # (b) point at shipped artefacts.
        self.assertIn(
            "hooks/cache-breakpoint-injector.sh", text,
            "Must reference shipped hook hooks/cache-breakpoint-injector.sh")
        self.assertIn(
            "skills/cache-audit/SKILL.md", text,
            "Must reference shipped skill skills/cache-audit/SKILL.md")
        # (c) Path-B advisory/log-only + cache-breakpoint-injector.sh:28-29 flip surface.
        self.assertRegex(
            text, r"advisory.*log-only|log-only.*advisory",
            "Must document Path-B advisory/log-only status")
        self.assertIn(
            "cache-breakpoint-injector.sh:28-29", text,
            "Must cite the single-file flip surface line range")
        # (d) ProjectDiscovery verbatim sentence template.
        self.assertIn(
            PROJECTDISCOVERY_SENTENCE, text,
            "Must cite ProjectDiscovery's 70% case study verbatim "
            "and justify 0.60 target")
        # (e) BOTH upstream dependencies + 3 follow-up tickets.
        self.assertIn(
            "modified_tool_input", text,
            "Must enumerate `modified_tool_input` schema dependency")
        self.assertRegex(
            text, r"orchestrator.*splice.*rules/core\.md|"
                  r"rules/core\.md.*splice.*orchestrator|"
                  r"splice.+rules/core\.md",
            "Must enumerate orchestrator-side splice of rules/core.md")
        for ticket in FOLLOWUP_TICKETS:
            self.assertIn(
                ticket, text,
                f"Must name follow-up ticket `{ticket}`")
        # (f) Agent tool only scope.
        self.assertIn(
            AGENT_TOOL_ONLY_SENTENCE, text,
            "Must state Agent-tool-only scope verbatim")

    def test_measurement_surface_fourth_bullet_and_see_also_link_present(self):
        text = DOC.read_text()
        # § Per-Spawn Measurement Surface — fourth bullet citing cache hook + skill.
        section_match = re.search(
            r"##\s*Per-Spawn Measurement Surface\s*\n(.+?)(?=\n##\s|\Z)",
            text, re.DOTALL)
        self.assertIsNotNone(
            section_match,
            "Must have `## Per-Spawn Measurement Surface` section")
        section = section_match.group(1)
        bullets = [b for b in section.splitlines() if b.lstrip().startswith("- ")]
        self.assertGreaterEqual(
            len(bullets), 4,
            "Per-Spawn Measurement Surface must have ≥4 bullets")
        # At least one bullet names the new hook AND at least one names the skill.
        # (Either combined in one bullet or split across bullets.)
        joined = " ".join(bullets)
        self.assertIn(
            "hooks/cache-breakpoint-injector.sh", joined,
            "A bullet under Per-Spawn Measurement Surface must cite "
            "hooks/cache-breakpoint-injector.sh")
        self.assertIn(
            "skills/cache-audit/SKILL.md", joined,
            "A bullet under Per-Spawn Measurement Surface must cite "
            "skills/cache-audit/SKILL.md")
        # § See Also — must link cache-audit skill.
        see_also_match = re.search(
            r"##\s*See Also\s*\n(.+?)(?=\n##\s|\Z)",
            text, re.DOTALL)
        self.assertIsNotNone(
            see_also_match, "Must have `## See Also` section")
        self.assertIn(
            "skills/cache-audit/SKILL.md", see_also_match.group(1),
            "See Also must link skills/cache-audit/SKILL.md")


if __name__ == "__main__":
    unittest.main()

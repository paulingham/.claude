"""Slice A AC-A9 — /cache-audit report's `## Notes` section discloses the 3
deferred anchors by reason enum exactly matching resolver payload, AND
discloses the missing orchestrator-side splice dependency for rules-core-tail.

Asserted against the SKILL.md `## Notes` section body — this is the canonical
rendering template the aggregator copies verbatim.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "cache-audit" / "SKILL.md"

REQUIRED_REASON_ENUMS = (
    "persona-marker-deferred",
    "protocol-splice-not-implemented",
    "outside-hook-surface-v2.1.140",
)

SPLICE_DEPENDENCY_PHRASES = (
    "modified_tool_input",
    "rules/core.md",
    "prompt-caching-rules-core-splice",
)


class CacheAuditDisclosureNotes(unittest.TestCase):
    def test_notes_section_discloses_three_deferred_reasons_and_splice_dependency(self):
        text = SKILL.read_text()
        # Pull the Notes section body.
        match = re.search(
            r"##\s*Notes\s*\n(.+?)(?=\n##\s|\Z)",
            text, re.DOTALL)
        self.assertIsNotNone(
            match, "SKILL.md must have a `## Notes` section")
        body = match.group(1)
        # Three reason enums appear verbatim.
        for reason in REQUIRED_REASON_ENUMS:
            self.assertIn(
                reason, body,
                f"`## Notes` must disclose deferred anchor reason `{reason}` "
                "verbatim (must match resolver payload).")
        # Splice-dependency disclosure: all three phrases appear in the body.
        for phrase in SPLICE_DEPENDENCY_PHRASES:
            self.assertIn(
                phrase, body,
                f"`## Notes` must name the splice dependency: missing `{phrase}`")


if __name__ == "__main__":
    unittest.main()

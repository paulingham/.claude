"""Skill-directory catalog completeness.

CLAUDE.md was pruned to a pointer (commit b606d59); the canonical Skill
Directory catalog (with /harness:-prefixed rows) lives in
protocols/skill-directory.md under `## Active Skills`. These tests assert
`/harness:pdr-rtv` and `/harness:cache-audit` rows are present with their
verdicts.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRECTORY_PROTOCOL = REPO_ROOT / "protocols" / "skill-directory.md"


def _active_skills_section() -> str:
    """Return the `## Active Skills` table body from protocols/skill-directory.md."""
    text = SKILL_DIRECTORY_PROTOCOL.read_text()
    match = re.search(
        r"##\s*Active Skills\s*\n(.+?)(?=\n##\s|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


def _row_for(section: str, skill: str):
    for line in section.splitlines():
        if skill in line and line.lstrip().startswith("|"):
            return line
    return None


class PdrRtvInGlobalSkillTable(unittest.TestCase):
    def test_pdr_rtv_in_global_skill_table(self):
        section = _active_skills_section()
        self.assertTrue(section, "Could not locate ## Active Skills section")
        self.assertIsNotNone(
            _row_for(section, "/harness:pdr-rtv"),
            "skill directory must contain a `/harness:pdr-rtv` row")

    def test_pdr_rtv_emits_correct_verdicts(self):
        section = _active_skills_section()
        row = _row_for(section, "/harness:pdr-rtv")
        self.assertIsNotNone(row, "/harness:pdr-rtv row not found")
        self.assertIn(
            "PDR_WINNER_SELECTED", row,
            "/harness:pdr-rtv row must list PDR_WINNER_SELECTED verdict")
        self.assertIn(
            "PDR_NO_CONSENSUS", row,
            "/harness:pdr-rtv row must list PDR_NO_CONSENSUS verdict")


class CacheAuditSkillListedInActiveTableWithCorrectVerdict(unittest.TestCase):
    """/harness:cache-audit row tied to verdict `CACHE_AUDIT_READY`."""

    def test_cache_audit_skill_listed_in_active_table_with_correct_verdict(self):
        section = _active_skills_section()
        self.assertTrue(
            section,
            "protocols/skill-directory.md must have an `## Active Skills` section")
        row = _row_for(section, "/harness:cache-audit")
        self.assertIsNotNone(
            row,
            "protocols/skill-directory.md Active Skills must list "
            "`/harness:cache-audit`")
        self.assertIn(
            "CACHE_AUDIT_READY", row,
            "/harness:cache-audit row must list verdict `CACHE_AUDIT_READY`")


if __name__ == "__main__":
    unittest.main()

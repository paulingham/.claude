"""Slice 3 AC12 — /pdr-rtv listed in global CLAUDE.md skill directory.

The skill directory in `~/.claude/CLAUDE.md` must include a row for
`/pdr-rtv`. The Phase column reads "Build dispatch variant" and the
Tunable column is "No" (PDR-RTV is a dispatch variant, not an agent
role).
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GLOBAL_CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
SKILL_DIRECTORY_PROTOCOL = REPO_ROOT / "protocols" / "skill-directory.md"


def _skill_directory_section() -> str:
    """Return the contents of the `### Skill Directory` section in CLAUDE.md."""
    text = GLOBAL_CLAUDE_MD.read_text()
    match = re.search(
        r"###\s+Skill Directory(.+?)(?=\n###\s+|\n##\s+|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


def _active_skills_section() -> str:
    """Return the `## Active Skills` table body from protocols/skill-directory.md."""
    text = SKILL_DIRECTORY_PROTOCOL.read_text()
    match = re.search(
        r"##\s*Active Skills\s*\n(.+?)(?=\n##\s|\Z)",
        text, re.DOTALL)
    return match.group(1) if match else ""


class PdrRtvInGlobalSkillTable(unittest.TestCase):
    def test_pdr_rtv_in_global_skill_table(self):
        section = _skill_directory_section()
        self.assertTrue(section, "Could not locate ### Skill Directory section")
        # Find a row that contains the literal `/pdr-rtv` skill name in the
        # first column (between backticks).
        pdr_rtv_row = None
        for line in section.splitlines():
            if "/pdr-rtv" in line and line.lstrip().startswith("|"):
                pdr_rtv_row = line
                break
        self.assertIsNotNone(
            pdr_rtv_row,
            "CLAUDE.md skill directory must contain a `/pdr-rtv` row")

    def test_pdr_rtv_emits_correct_verdicts(self):
        section = _skill_directory_section()
        # Find the row content; the verdict column lists the verdicts.
        for line in section.splitlines():
            if "/pdr-rtv" in line and line.lstrip().startswith("|"):
                # Verdict column should mention both verdicts.
                self.assertIn(
                    "PDR_WINNER_SELECTED", line,
                    "/pdr-rtv row must list PDR_WINNER_SELECTED verdict")
                self.assertIn(
                    "PDR_NO_CONSENSUS", line,
                    "/pdr-rtv row must list PDR_NO_CONSENSUS verdict")
                return
        self.fail("/pdr-rtv row not found")


class CacheAuditSkillListedInActiveTableWithCorrectVerdict(unittest.TestCase):
    """Slice C AC-C5 — /cache-audit row in `protocols/skill-directory.md`
    Active Skills table tied to verdict `CACHE_AUDIT_READY`.
    """

    def test_cache_audit_skill_listed_in_active_table_with_correct_verdict(self):
        section = _active_skills_section()
        self.assertTrue(
            section,
            "protocols/skill-directory.md must have an `## Active Skills` section")
        cache_audit_row = None
        for line in section.splitlines():
            if "/cache-audit" in line and line.lstrip().startswith("|"):
                cache_audit_row = line
                break
        self.assertIsNotNone(
            cache_audit_row,
            "protocols/skill-directory.md Active Skills must list `/cache-audit`")
        self.assertIn(
            "CACHE_AUDIT_READY", cache_audit_row,
            "/cache-audit row must list verdict `CACHE_AUDIT_READY`")


if __name__ == "__main__":
    unittest.main()

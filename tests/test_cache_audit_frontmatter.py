"""Slice A AC-A4 — skills/cache-audit/SKILL.md frontmatter literals.

Mirrors skills/cost-report/SKILL.md:1-8 shape exactly. The frontmatter MUST
contain these literal values (not just field names):
  - verdict: CACHE_AUDIT_READY
  - phase: utility
  - dispatch: skill-tool

Mirrors tests/test_pbt_skill_frontmatter.py / tests/test_pbt_engineer_frontmatter.py shape.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "cache-audit" / "SKILL.md"


def _frontmatter():
    text = SKILL.read_text()
    match = re.match(r"^---\n(.*?)\n---\s*\n", text, re.DOTALL)
    return match.group(1) if match else ""


class CacheAuditSkillFrontmatter(unittest.TestCase):
    def test_cache_audit_skill_frontmatter_has_required_literal_values(self):
        self.assertTrue(SKILL.is_file(),
                        f"skills/cache-audit/SKILL.md not found at {SKILL}")
        fm = _frontmatter()
        self.assertTrue(fm, "skills/cache-audit/SKILL.md missing frontmatter")
        # verdict: CACHE_AUDIT_READY (with optional surrounding quotes).
        self.assertTrue(
            re.search(r'^verdict:\s*"?CACHE_AUDIT_READY"?\s*$', fm, re.MULTILINE),
            "frontmatter must declare `verdict: CACHE_AUDIT_READY`")
        # phase: utility
        self.assertTrue(
            re.search(r'^phase:\s*"?utility"?\s*$', fm, re.MULTILINE),
            "frontmatter must declare `phase: utility`")
        # dispatch: skill-tool
        self.assertTrue(
            re.search(r'^dispatch:\s*"?skill-tool"?\s*$', fm, re.MULTILINE),
            "frontmatter must declare `dispatch: skill-tool`")


if __name__ == "__main__":
    unittest.main()

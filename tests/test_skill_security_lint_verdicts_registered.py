"""Verdict registration test for skill-security-lint (GP-P4-2).

Mirrors tests/test_verdict_catalog_new_entries.py — asserts that both
SKILL_LINT_CLEAN and SKILL_LINT_FLAGGED appear in protocols/verdict-catalog.md
and are attributed to the skill-security-lint emitter.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOG = REPO_ROOT / "protocols" / "verdict-catalog.md"


class SkillSecurityLintVerdictsRegistered(unittest.TestCase):
    def test_skill_lint_verdicts_in_catalog(self):
        text = CATALOG.read_text()
        for verdict in ("SKILL_LINT_CLEAN", "SKILL_LINT_FLAGGED"):
            self.assertIn(
                f"`{verdict}`", text,
                f"verdict `{verdict}` must be declared in protocols/verdict-catalog.md")

    def test_skill_lint_verdicts_attributed_to_skill_security_lint_emitter(self):
        text = CATALOG.read_text()
        for line in text.splitlines():
            if "SKILL_LINT_" in line:
                self.assertIn(
                    "skill-security-lint", line,
                    f"row `{line}` should attribute emitter `skill-security-lint`")


if __name__ == "__main__":
    unittest.main()

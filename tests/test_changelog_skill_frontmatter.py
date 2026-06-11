"""GP-P3-1 — `/changelog` skill contract + pr-creation wiring guards.

The harness audit flagged Technical Writing as WEAK: `pr-creation` produced a PR
but no changelog/release-notes generation. This skill closes that gap. These
tests pin three invariants:

1. The new SKILL.md is parseable by the harness skill-loader contract
   (YAML frontmatter, `name == "changelog"`, non-empty description).
2. The description starts with the model-invocation cue `"Use when user wants
   to ..."` — the same property every reliably-auto-invoking skill shares
   (see tests/test_pr_creation_skill_frontmatter.py).
3. `pr-creation` references `/harness:changelog`, so the Ship phase actually
   invokes it rather than leaving the narrative to model discretion.
"""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "changelog" / "SKILL.md"
PR_CREATION = ROOT / "skills" / "pr-creation" / "SKILL.md"


def _frontmatter(path):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, f"{path} has no YAML frontmatter block"
    return yaml.safe_load(match.group(1))


class ChangelogSkillFrontmatter(unittest.TestCase):
    def test_skill_file_exists(self):
        self.assertTrue(SKILL.exists(), f"missing {SKILL}")

    def test_name_is_changelog(self):
        self.assertEqual(_frontmatter(SKILL).get("name"), "changelog")

    def test_description_non_empty(self):
        self.assertTrue((_frontmatter(SKILL).get("description") or "").strip())

    def test_description_starts_with_use_when_cue(self):
        description = _frontmatter(SKILL).get("description", "")
        self.assertTrue(
            description.startswith("Use when user wants to ")
            or description.startswith("Use when user wants "),
            msg=(
                'description must start with the model-invocation cue '
                f'"Use when user wants to ...". Got: {description!r}'
            ),
        )


class PrCreationInvokesChangelog(unittest.TestCase):
    def test_pr_creation_references_changelog_skill(self):
        body = PR_CREATION.read_text()
        self.assertIn(
            "/harness:changelog",
            body,
            msg=(
                "skills/pr-creation/SKILL.md must invoke /harness:changelog so "
                "the Ship phase generates a changelog entry + PR narrative."
            ),
        )


if __name__ == "__main__":
    unittest.main()

"""Tests for CONTRIBUTING.md and its authoring guide companions (Slice B, ACs B1-B7).

These verify the contributor documentation exists, contains the correct
must-run commands, references the templates dir, and that the skills/README.md
breadcrumb exists but does NOT add to the skill count.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"


class ContributingDocPresence(unittest.TestCase):
    """B1 — CONTRIBUTING.md exists at repo root."""

    def test_contributing_md_exists_at_repo_root(self):
        self.assertTrue(CONTRIBUTING.exists(), "CONTRIBUTING.md missing at repo root")


class ContributingDocSections(unittest.TestCase):
    """B2 — has EASY-path and GATED-path sections."""

    def _text(self) -> str:
        return CONTRIBUTING.read_text()

    def test_contributing_documents_easy_vs_gated_paths(self):
        text = self._text()
        self.assertIn("EASY", text,
                      "CONTRIBUTING.md must document the EASY contributor path")
        self.assertIn("GATED", text,
                      "CONTRIBUTING.md must document the GATED contributor path")


class ContributingMustRunCommands(unittest.TestCase):
    """B3 — both literal must-run commands are present."""

    def _text(self) -> str:
        return CONTRIBUTING.read_text()

    def test_contributing_lists_both_must_run_commands(self):
        text = self._text()
        self.assertIn("bash tests/shell/run.sh", text,
                      "CONTRIBUTING.md must contain 'bash tests/shell/run.sh'")
        expected_pytest = (
            'pytest -k "readme or verdict or catalog or inventory'
            ' or stop_hook or counts_match or agent_table or registration"'
        )
        self.assertIn(expected_pytest, text,
                      f"CONTRIBUTING.md must contain the scoped pytest command")


class ContributingHookRegistration(unittest.TestCase):
    """B4 — names hooks.json AND settings.json + mentions scripts."""

    def _text(self) -> str:
        return CONTRIBUTING.read_text()

    def test_contributing_documents_dual_hook_registration(self):
        text = self._text()
        self.assertIn("hooks.json", text,
                      "CONTRIBUTING.md must mention hooks.json")
        self.assertIn("settings.json", text,
                      "CONTRIBUTING.md must mention settings.json")
        self.assertIn("scripts/", text,
                      "CONTRIBUTING.md must reference the scripts/ directory")


class ContributingTemplatesDir(unittest.TestCase):
    """B5 — references templates/ directory."""

    def _text(self) -> str:
        return CONTRIBUTING.read_text()

    def test_contributing_points_at_templates_dir(self):
        text = self._text()
        self.assertIn("templates/", text,
                      "CONTRIBUTING.md must reference the templates/ directory")


class AuthoringGuidesPresence(unittest.TestCase):
    """B6 — one authoring guide exists per surface (skill, agent, hook)."""

    def test_authoring_guides_exist_for_three_surfaces(self):
        skill_guide = REPO_ROOT / "templates" / "skill-reference" / "AUTHORING.md"
        agent_guide = REPO_ROOT / "templates" / "AGENT_AUTHORING.md"
        hook_guide = REPO_ROOT / "templates" / "HOOK_AUTHORING.md"
        self.assertTrue(skill_guide.exists(), f"missing skill authoring guide: {skill_guide}")
        self.assertTrue(agent_guide.exists(), f"missing agent authoring guide: {agent_guide}")
        self.assertTrue(hook_guide.exists(), f"missing hook authoring guide: {hook_guide}")


class SkillsReadmeBreadcrumb(unittest.TestCase):
    """B7 — skills/README.md exists and is NOT matched by skills/*/SKILL.md glob."""

    def test_skills_readme_breadcrumb_exists_and_is_not_a_skill(self):
        readme = REPO_ROOT / "skills" / "README.md"
        self.assertTrue(readme.exists(), "skills/README.md breadcrumb is missing")

        text = readme.read_text()
        self.assertIn("CONTRIBUTING.md", text,
                      "skills/README.md must point at CONTRIBUTING.md")
        self.assertTrue(
            "new-skill.sh" in text or "scripts/" in text,
            "skills/README.md must reference new-skill.sh or scripts/"
        )

        globbed = list(REPO_ROOT.glob("skills/*/SKILL.md"))
        self.assertNotIn(readme, globbed,
                         "skills/README.md must NOT appear in skills/*/SKILL.md glob")


if __name__ == "__main__":
    unittest.main()

"""Tests for contributor-facing templates placed under templates/.

These assert the templates exist at non-globbed paths (Slice A ACs A1-A6).
The critical invariant is that NONE of the three templates are reachable
by the skill-count glob, agent-table glob, or hook-registration find —
so the CI pinning guards stay green without any test edits.
"""
import glob
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class SkillReferenceTemplateLocation(unittest.TestCase):
    """A1 — template exists AND is invisible to the skill-count glob."""

    def test_skill_reference_template_exists_at_nonglobbed_path(self):
        template_path = REPO_ROOT / "templates" / "skill-reference" / "SKILL.md"
        self.assertTrue(template_path.exists(), f"missing: {template_path}")
        globbed = list(REPO_ROOT.glob("skills/*/SKILL.md"))
        self.assertNotIn(template_path, globbed,
                         "template was picked up by the skills/*/SKILL.md glob")


class SkillReferenceTemplateFrontmatter(unittest.TestCase):
    """A2 — frontmatter has name+description; NO verdict/phase/dispatch."""

    def _parse_frontmatter(self, path: Path) -> dict:
        text = path.read_text()
        if not text.startswith("---"):
            return {}
        end = text.find("---", 3)
        if end == -1:
            return {}
        import yaml
        return yaml.safe_load(text[4:end]) or {}

    def test_skill_reference_frontmatter_has_name_desc_only(self):
        template_path = REPO_ROOT / "templates" / "skill-reference" / "SKILL.md"
        fm = self._parse_frontmatter(template_path)
        self.assertIn("name", fm)
        self.assertIn("description", fm)
        for forbidden in ("verdict", "phase", "dispatch"):
            self.assertNotIn(forbidden, fm,
                             f"template frontmatter must not contain '{forbidden}'")


class AgentTemplateLocation(unittest.TestCase):
    """A3 — agent template exists AND is invisible to the agent-table glob."""

    def test_agent_template_exists_at_nonglobbed_path(self):
        template_path = REPO_ROOT / "templates" / "agent-template.md"
        self.assertTrue(template_path.exists(), f"missing: {template_path}")
        agents_dir = REPO_ROOT / "agents"
        globbed = list(agents_dir.glob("*.md"))
        self.assertNotIn(template_path, globbed,
                         "template was picked up by agents/*.md glob")


class AgentTemplateFrontmatter(unittest.TestCase):
    """A4 — agent template frontmatter has required fields."""

    def _parse_frontmatter(self, path: Path) -> dict:
        text = path.read_text()
        if not text.startswith("---"):
            return {}
        end = text.find("---", 3)
        if end == -1:
            return {}
        import yaml
        return yaml.safe_load(text[4:end]) or {}

    def test_agent_template_frontmatter_contract(self):
        template_path = REPO_ROOT / "templates" / "agent-template.md"
        fm = self._parse_frontmatter(template_path)
        for required in ("name", "description", "tools", "model", "maxTurns"):
            self.assertIn(required, fm,
                          f"agent template missing required field: '{required}'")


class HookTemplateLocation(unittest.TestCase):
    """A5 — hook template exists AND is invisible to hooks find -maxdepth 1 *.sh."""

    def test_hook_template_at_nonglobbed_path(self):
        template_path = REPO_ROOT / "templates" / "hook-template.sh"
        self.assertTrue(template_path.exists(), f"missing: {template_path}")
        result = subprocess.run(
            ["find", str(REPO_ROOT / "hooks"), "-maxdepth", "1", "-name", "*.sh"],
            capture_output=True, text=True, check=True
        )
        found_paths = result.stdout.strip().splitlines()
        self.assertNotIn(str(template_path), found_paths,
                         "hook template was found by the hooks -maxdepth 1 *.sh find")


if __name__ == "__main__":
    unittest.main()

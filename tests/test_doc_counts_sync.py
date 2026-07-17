"""ACs A1-A9: tests for scripts/sync_doc_counts.py generator."""
import importlib
import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).parent.parent
_SCRIPT_PATH = REPO_ROOT / "scripts" / "sync_doc_counts.py"

# WHY: import script as module so we can call internal helpers directly without
# needing an installed package.
spec = importlib.util.spec_from_file_location("sync_doc_counts", _SCRIPT_PATH)
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class ComputeCounts(unittest.TestCase):
    """A1: compute_counts returns skills=73 / agents=19 for live repo."""

    def test_compute_counts_matches_ac9_glob_rule(self):
        counts = sync.compute_counts(REPO_ROOT)
        self.assertEqual(counts["skills"], 73)
        self.assertEqual(counts["agents"], 19)


class RenderReadme(unittest.TestCase):
    """A2-A3: render_readme rewrites all four count tokens."""

    _SKILL_README = (
        "# Arch\n"
        "  agents/            # 19 specialized agent definitions\n"
        "  skills/            # 70 skills — the procedural workflows\n"
        "## Skills (70)\n"
        "The full skill catalogue (70 skills, grouped by phase) lives in\n"
    )

    def test_render_rewrites_all_three_skill_tokens(self):
        """A2: heading, arch-diagram comment, and prose are all rewritten."""
        text = self._SKILL_README
        result = sync.render_readme(text, {"skills": 99, "agents": 19})
        self.assertIn("## Skills (99)", result)
        self.assertIn("# 99 skills", result)
        self.assertIn("(99 skills, grouped by phase)", result)

    def test_render_rewrites_agent_token(self):
        """A3: specialized-agent arch comment is rewritten."""
        text = self._SKILL_README
        result = sync.render_readme(text, {"skills": 70, "agents": 25})
        self.assertIn("# 25 specialized agent", result)


class CheckFunction(unittest.TestCase):
    """A4-A7: check() / write() correctness + fail-closed behaviour."""

    def _make_readme(self, tmpdir, skills, agents):
        """Write a minimal README with all four tokens."""
        content = (
            "# Arch\n"
            f"  agents/            # {agents} specialized agent definitions\n"
            f"  skills/            # {skills} skills — the procedural workflows\n"
            f"## Skills ({skills})\n"
            f"The full skill catalogue ({skills} skills, grouped by phase) lives in\n"
        )
        p = pathlib.Path(tmpdir) / "README.md"
        p.write_text(content)
        return p

    def test_check_returns_zero_when_docs_current(self):
        """A4: check() exits 0 when README already has correct counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            td = pathlib.Path(tmpdir)
            # build minimal repo structure
            skills_dir = td / "skills" / "my-skill"
            skills_dir.mkdir(parents=True)
            (skills_dir / "SKILL.md").write_text("# skill")
            agents_dir = td / "agents"
            agents_dir.mkdir()
            (agents_dir / "my-agent.md").write_text("# agent")
            self._make_readme(tmpdir, skills=1, agents=1)
            rc = sync.check(td)
            self.assertEqual(rc, 0)

    def test_check_returns_nonzero_on_drift(self):
        """A5: check() exits nonzero when README count is wrong (Law-8a gate fires)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            td = pathlib.Path(tmpdir)
            skills_dir = td / "skills" / "my-skill"
            skills_dir.mkdir(parents=True)
            (skills_dir / "SKILL.md").write_text("# skill")
            agents_dir = td / "agents"
            agents_dir.mkdir()
            (agents_dir / "my-agent.md").write_text("# agent")
            # Write README with WRONG counts (drift)
            self._make_readme(tmpdir, skills=99, agents=99)
            rc = sync.check(td)
            self.assertNotEqual(rc, 0)

    def test_check_refuses_when_readme_missing(self):
        """A6: check() returns nonzero (refuse) when README.md does not exist (Law-8b)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            td = pathlib.Path(tmpdir)
            (td / "skills").mkdir()
            (td / "agents").mkdir()
            # README intentionally absent
            rc = sync.check(td)
            self.assertNotEqual(rc, 0)

    @unittest.skipIf(os.getuid() == 0, "chmod 000 has no effect as root")
    def test_check_refuses_when_skills_dir_unreadable(self):
        """A7: check() returns nonzero (refuse) when skills dir is unreadable (Law-8b)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            td = pathlib.Path(tmpdir)
            skills_dir = td / "skills"
            skills_dir.mkdir()
            (td / "agents").mkdir()
            self._make_readme(tmpdir, skills=0, agents=0)
            skills_dir.chmod(0o000)
            try:
                rc = sync.check(td)
                self.assertNotEqual(rc, 0)
            finally:
                skills_dir.chmod(0o755)


class MainCli(unittest.TestCase):
    """A8: end-to-end --check on live repo exits 0 (CI staleness gate)."""

    def test_main_check_on_live_repo_is_green(self):
        """A8: main(--check --repo-root <live>) == 0 after generator is correct."""
        rc = sync.main(["--check", "--repo-root", str(REPO_ROOT)])
        self.assertEqual(
            rc, 0,
            "sync_doc_counts --check on live repo is non-zero; "
            "README.md has drifted from filesystem counts. "
            "Run: python3 scripts/sync_doc_counts.py --write"
        )


class RenderToleratesMinimalReadme(unittest.TestCase):
    """A9 (HIGH): render_readme must NOT raise and must NOT inject missing tokens."""

    def test_render_tolerates_minimal_readme_two_tokens(self):
        """A9: a README with ONLY # N skills + ## Skills (N) (no prose token)
        gets those two rewritten but raises nothing and injects nothing extra.
        Mirrors the C11 fake_repo at test_scaffolding_scripts.bats:240.
        """
        minimal = "# Arch\n  skills/  # 1 skills — blah\n## Skills (1)\nMore text.\n"
        result = sync.render_readme(minimal, {"skills": 2, "agents": 5})
        # Both present tokens must be rewritten
        self.assertIn("# 2 skills", result)
        self.assertIn("## Skills (2)", result)
        # The absent prose token must NOT be injected
        self.assertNotIn("(2 skills, grouped", result)
        self.assertNotIn("(2 skills,", result)
        # Must not raise — reaching here proves it

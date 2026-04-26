"""Patch-critic role tests (Wave 2 D2).

Validates the structural contract of the patch-critic role added to the Final
Gate Team. Mirrors `tests/test_skill_md_honesty.py` shape: documentation-level
assertions on the agent + skill + protocol files.

The patch-critic evaluates candidate patches by test results + diff (NOT SOLID
— that is the code-reviewer's job). Inspired by SWE-bench top scaffolds where
a critic step distinguishes high-scoring patches from regressions.
"""
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_MD = REPO_ROOT / "agents" / "patch-critic.md"
SKILL_MD = REPO_ROOT / "skills" / "patch-critique" / "SKILL.md"
PARALLEL_PROTOCOL = REPO_ROOT / "rules" / "parallel-dispatch-protocol.md"
PIPELINE_PROTOCOL = REPO_ROOT / "rules" / "pipeline-protocol.md"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
README_MD = REPO_ROOT / "README.md"


class PatchCriticAgentDefinition(unittest.TestCase):
    def test_agent_file_exists(self):
        self.assertTrue(AGENT_MD.exists(), f"missing {AGENT_MD}")

    def test_advisor_pairing_sonnet_executor_opus_advisor(self):
        text = AGENT_MD.read_text()
        self.assertIn("executor: claude-sonnet-4-6", text)
        self.assertIn("advisor: claude-opus-4-7", text)

    def test_read_only_tool_surface(self):
        text = AGENT_MD.read_text()
        for forbidden in ("Write", "Edit", "MultiEdit"):
            self.assertIn(forbidden, _disallowed_block(text),
                          f"{forbidden} must be disallowed for read-only critic")

    def test_does_not_overlap_with_code_reviewer(self):
        text = AGENT_MD.read_text().lower()
        # Critic explicitly does NOT do SOLID/DRY — that's code-reviewer's job.
        self.assertIn("not solid", text.replace("-", " "))


class PatchCritiqueSkill(unittest.TestCase):
    def test_skill_file_exists(self):
        self.assertTrue(SKILL_MD.exists(), f"missing {SKILL_MD}")

    def test_verdicts_declared(self):
        text = SKILL_MD.read_text()
        self.assertIn("PATCH_APPROVED", text)
        self.assertIn("PATCH_REJECTED", text)

    def test_rubric_covers_required_dimensions(self):
        text = SKILL_MD.read_text().lower()
        # Rubric: tests cover the change, diff minimal vs spec,
        # no obvious regressions visible from diff, no incidental refactor.
        self.assertIn("tests cover", text)
        self.assertIn("minimal", text)
        self.assertIn("regression", text)
        self.assertIn("incidental", text)

    def test_rejection_returns_to_fix_engineer_not_user(self):
        text = SKILL_MD.read_text().lower()
        self.assertIn("fix-engineer", text)
        # Autonomous: never escalates to user on PATCH_REJECTED.
        self.assertNotIn("escalate to user", text)

    def test_inputs_documented(self):
        text = SKILL_MD.read_text().lower()
        for required_input in ("candidate diff", "test output", "intake spec"):
            self.assertIn(required_input, text)

    def test_explicitly_excludes_solid(self):
        text = SKILL_MD.read_text().lower()
        # The critic must NOT duplicate code-reviewer's SOLID/DRY audit.
        self.assertTrue(
            "not solid" in text.replace("-", " ") or "no solid" in text or "exclude solid" in text,
            "skill must explicitly disclaim SOLID/DRY scope")


class FinalGateTeamWiring(unittest.TestCase):
    def test_parallel_dispatch_lists_patch_critic_in_final_gate(self):
        text = PARALLEL_PROTOCOL.read_text()
        final_gate_section = _slice_section(text, "### Final Gate Team")
        self.assertIn("patch-critic", final_gate_section)
        self.assertIn("/patch-critique", final_gate_section)
        self.assertIn("PATCH_APPROVED", final_gate_section)

    def test_final_gate_runs_four_phases_in_parallel(self):
        text = PARALLEL_PROTOCOL.read_text()
        final_gate_section = _slice_section(text, "### Final Gate Team")
        # All four teammates must appear in the same Final Gate Team table.
        for teammate in ("verify", "qa-test-strategy", "product-acceptance",
                         "patch-critique"):
            self.assertIn(teammate, final_gate_section,
                          f"Final Gate Team table missing {teammate}")

    def test_pipeline_protocol_includes_patch_critic_in_final_gate(self):
        text = PIPELINE_PROTOCOL.read_text()
        # The phase checklist must list /patch-critique alongside the other
        # Final Gate skills. PATCH_REJECTED is a hard gate on Ship.
        self.assertIn("/patch-critique", text)
        self.assertIn("PATCH_REJECTED", text)

    def test_runs_independently_no_shared_lock(self):
        # The Final Gate teammates each work read-only on the same final state.
        # No teammate writes to the working tree, so there is no lock contention.
        text = AGENT_MD.read_text()
        granted = _granted_tools_block(text)
        self.assertIn("Read", granted)
        # Granted tools must contain no write surface — Write/Edit/MultiEdit
        # appear only in disallowedTools.
        for write_tool in ("Write", "Edit", "MultiEdit"):
            self.assertNotIn(write_tool, granted,
                             f"{write_tool} must not be a granted tool for read-only critic")


class DocumentationUpdates(unittest.TestCase):
    def test_claude_md_agent_team_lists_patch_critic(self):
        text = CLAUDE_MD.read_text()
        agent_table = _slice_section(text, "### Agent Team")
        self.assertIn("patch-critic", agent_table)

    def test_readme_documents_patch_critic(self):
        text = README_MD.read_text()
        self.assertIn("patch-critic", text)
        self.assertIn("/patch-critique", text)


def _disallowed_block(frontmatter_text: str) -> str:
    match = re.search(r"disallowedTools:(.*?)(?:\n---|\Z)",
                      frontmatter_text, re.DOTALL)
    return match.group(1) if match else ""


def _granted_tools_block(frontmatter_text: str) -> str:
    # Match `tools:` (not `disallowedTools:`) up to the next top-level key.
    match = re.search(r"\ntools:(.*?)\n[a-zA-Z]", frontmatter_text, re.DOTALL)
    return match.group(1) if match else ""


def _slice_section(text: str, heading: str) -> str:
    idx = text.find(heading)
    if idx == -1:
        return ""
    next_heading = re.search(r"\n#{1,3} ", text[idx + len(heading):])
    end = idx + len(heading) + (next_heading.start() if next_heading else len(text))
    return text[idx:end]


if __name__ == "__main__":
    unittest.main()

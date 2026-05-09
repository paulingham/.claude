"""AC8 — `agents/patch-critic.md` documents tournament mode.

The patch-critic agent must carry a `## Tournament Mode` section that
specifies the `Mode: tournament` prompt token, the binary `WINNER:`
output spec, and an explicit non-overlap statement with single-critic /
multi-persona modes.

Pattern matches existing structural assertions in
`tests/test_patch_critic.py`.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_MD = REPO_ROOT / "agents" / "patch-critic.md"


class PatchCriticTournamentMode(unittest.TestCase):
    def setUp(self):
        self.assertTrue(AGENT_MD.exists(), f"missing {AGENT_MD}")
        self.text = AGENT_MD.read_text()

    def test_agent_md_documents_tournament_mode(self):
        """A `## Tournament Mode` section must exist."""
        self.assertIn("## Tournament Mode", self.text,
                      "patch-critic.md missing `## Tournament Mode` section")

    def test_tournament_mode_describes_prompt_token(self):
        """The section must reference the `Mode: tournament` prompt token."""
        self.assertIn("Mode: tournament", self.text,
                      "tournament mode docs must reference the `Mode: tournament` token")

    def test_tournament_mode_describes_binary_winner_output(self):
        """The section must specify the binary `WINNER:` output contract."""
        # Both `WINNER: A` and the verbal contract must be present.
        self.assertIn("WINNER:", self.text,
                      "tournament mode docs must reference the `WINNER:` output spec")

    def test_tournament_mode_explicit_non_overlap_with_other_modes(self):
        """The section must explicitly state non-overlap with single-critic / multi-persona."""
        # Locate the tournament-mode section body.
        section_start = self.text.find("## Tournament Mode")
        self.assertGreaterEqual(section_start, 0)
        # Find next H2 boundary to scope the search.
        next_h2 = self.text.find("\n## ", section_start + 1)
        section_body = self.text[section_start: next_h2 if next_h2 != -1 else len(self.text)]
        body_lower = section_body.lower()
        self.assertIn("single-critic", body_lower,
                      "tournament-mode body must mention single-critic mode for non-overlap")
        self.assertIn("multi-persona", body_lower,
                      "tournament-mode body must mention multi-persona mode for non-overlap")

    def test_tournament_mode_describes_summary_vs_summary_input(self):
        """Tournament mode is summary-vs-summary; legacy modes are diff-vs-spec."""
        section_start = self.text.find("## Tournament Mode")
        next_h2 = self.text.find("\n## ", section_start + 1)
        section_body = self.text[section_start: next_h2 if next_h2 != -1 else len(self.text)]
        body_lower = section_body.lower()
        self.assertIn("summary", body_lower,
                      "tournament-mode body must clarify summary-based input scope")


if __name__ == "__main__":
    unittest.main()

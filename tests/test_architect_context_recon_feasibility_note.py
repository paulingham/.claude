"""Slice slice-b-architect-feasibility-pass: architect-context-recon.md reserves
the Feasibility Finding section name.

AC from pipeline-state/plan-feasibility-finding/plan.md, slice-b:

- AC-B6: `agents/architect-context-recon.md` Output File section notes the architect
  appends `## Feasibility Finding` downstream and recon does NOT write it.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RECON_MD = REPO_ROOT / "agents" / "architect-context-recon.md"


def _read_recon_md() -> str:
    return RECON_MD.read_text()


class ReconOutputFeasibilityNote(unittest.TestCase):
    """AC-B6 — recon Output File section reserves the Feasibility Finding section."""

    def test_recon_output_reserves_feasibility_section(self):
        text = _read_recon_md()

        # Output File section must exist
        self.assertIn(
            "## Output File",
            text,
            "agents/architect-context-recon.md must contain '## Output File' section",
        )

        # Must mention ## Feasibility Finding as reserved downstream
        self.assertIn(
            "## Feasibility Finding",
            text,
            "agents/architect-context-recon.md Output File section must reserve "
            "'## Feasibility Finding' section name",
        )

        # Must state the architect (not recon) appends the section
        self.assertRegex(
            text,
            r"architect appends|architect.*appends",
            "agents/architect-context-recon.md must state the architect appends "
            "the ## Feasibility Finding section",
        )

        # Must state recon does NOT write it
        self.assertRegex(
            text,
            r"recon.*does not write|recon.*does NOT write|recon agent.*does not|does not write it",
            "agents/architect-context-recon.md must state recon does NOT write "
            "the ## Feasibility Finding section",
        )


if __name__ == "__main__":
    unittest.main()

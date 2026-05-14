"""Slice 3: orchestrator/agent-orchestration.md must contain `## Worktree Env Propagation`
H2 mandating that the orchestrator sets $CLAUDE_WORKTREE_PATH on every
Build-onward Agent dispatch.

AC3.13 / HIGH-PR1: this is the load-bearing contract for HEAD resolution
rule 1 in `hooks/verification-freshness-guard.sh`. Without it, the hook's
no_worktree_resolvable skip-clean path fires on every orchestrator-context
Final Gate / Ship spawn, defeating the Iron Law 2 enforcement.
"""
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "orchestrator" / "agent-orchestration.md"


class WorktreeEnvPropagationDoc(unittest.TestCase):
    def setUp(self):
        self.text = DOC.read_text()

    def test_doc_mandates_worktree_env_on_build_onward_dispatch(self):
        # H2 must exist verbatim.
        self.assertIn("## Worktree Env Propagation", self.text,
                      "orchestrator/agent-orchestration.md must contain "
                      "`## Worktree Env Propagation` H2 (AC3.13)")
        # The env var must be named.
        self.assertIn("$CLAUDE_WORKTREE_PATH", self.text)
        # The mandate phrasing — must apply to Build-onward dispatches.
        # The exact "Build-onward" phrase ties to plan.md AC3.13.
        self.assertRegex(self.text,
                         r"Build[- ]onward|every Build.*dispatch",
                         "doc must scope env propagation to Build-onward dispatches")

    def test_doc_references_freshness_guard_hook(self):
        # The reverse pointer back to the hook keeps the contract bidirectional.
        self.assertIn("verification-freshness-guard", self.text)

    def test_doc_references_iron_law_2(self):
        # Cross-reference to rules/core.md Iron Law 2.
        self.assertIn("Iron Law 2", self.text)


if __name__ == "__main__":
    unittest.main()
